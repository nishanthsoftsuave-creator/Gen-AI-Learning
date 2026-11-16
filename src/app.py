import json
import logging
import shutil
import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agentic_bridge import run_agent, run_normal_workflow, run_multi_agent
from rag import retrieve_documents, generate_answer, GROQ_MODEL
from tracing import build_spans, create_trace_id, save_trace
from vector_store import store_embeddings


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"
UPLOAD_DIR = BASE_DIR / "uploads"
STATUS_FILE = UPLOAD_DIR / "status.json"

UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="RAG Document Q&A")
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if (FRONTEND_DIST_DIR / "assets").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST_DIR / "assets"),
        name="assets",
    )


class QuestionRequest(BaseModel):
    question: str
    user_ref: str | None = None  # hashed employee id; never a raw name


class CompareRequest(BaseModel):
    question: str


def read_status():
    if not STATUS_FILE.exists():
        return {
            "ready": False,
            "filename": None,
            "chunks": 0,
        }

    return json.loads(STATUS_FILE.read_text(encoding="utf-8"))


def write_status(filename, chunks):
    STATUS_FILE.write_text(
        json.dumps(
            {
                "ready": True,
                "filename": filename,
                "chunks": chunks,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


@app.get("/")
def home():
    index_file = FRONTEND_DIST_DIR / "index.html"

    if not index_file.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                "Frontend build not found. Run `npm install && npm run build` "
                "inside the frontend/ directory."
            ),
        )

    return FileResponse(index_file)


@app.get("/status")
def status():
    return read_status()


@app.post("/upload")
def upload_document(file: UploadFile = File(...)):
    filename = Path(file.filename).name if file.filename else ""

    if not filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    saved_path = UPLOAD_DIR / filename

    with saved_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result = store_embeddings(
            pdf_path=saved_path,
            reset=True,
            verbose=False,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process the document: {error}",
        ) from error

    write_status(filename, result["chunks"])

    return {
        "message": "Document uploaded and processed.",
        "filename": filename,
        "chunks": result["chunks"],
    }


@app.post("/ask")
def ask_question(payload: QuestionRequest):
    question = payload.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Please enter a question.")

    status_data = read_status()

    if not status_data.get("ready"):
        raise HTTPException(
            status_code=400,
            detail="Upload a PDF document before asking a question.",
        )

    retrieval_started = time.perf_counter()
    documents = retrieve_documents(question)
    retrieval_seconds = time.perf_counter() - retrieval_started

    if not documents:
        raise HTTPException(
            status_code=400,
            detail="No document content is available yet. Please upload a PDF.",
        )

     # Generate answer and capture metadata needed for tracing.
    answer, prompt, temperature, usage = generate_answer(
        question,
        documents,
        include_usage=True,
    )

    # Create and save a trace for this API request.
    trace_id = create_trace_id()

    save_trace(
        trace_id=trace_id,
        question=question,
        prompt=prompt,
        retrieved_chunks=documents,
        model=GROQ_MODEL,
        temperature=temperature,
        raw_output=answer,
        user_ref=payload.user_ref,
        spans=build_spans(GROQ_MODEL, retrieval_seconds, usage),
    )

    # API response must contain only the answer string for the frontend
    # Markdown renderer, while sources remain available to the UI.

    return {
        "question": question,
        "answer": answer,
        "filename": status_data.get("filename"),
        "sources": documents,
    }


def _serialize_run(result):
    return {
        "answer": result["answer"],
        "iterations": result["iterations"],
        "tool_calls": [
            {
                "tool": call["tool"],
                "arguments": call.get(
                    "arguments",
                    {key: call[key] for key in ("worker", "task") if key in call},
                ),
            }
            for call in result["tool_calls"]
        ],
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "total_tokens": result["total_tokens"],
        "cost": result["cost"],
        "elapsed_seconds": result["elapsed_seconds"],
        "termination_reason": result["termination_reason"],
        "trace_id": result["trace_id"],
    }


def _pick_winner(runs):
    """Compare efficiency only; this does not grade answer correctness."""
    clean_runs = [run for run in runs if run["termination_reason"] == "COMPLETED"]
    if not clean_runs:
        return {"winner": None, "reason": "All workflows failed; check the backend terminal for details."}
    candidates = clean_runs or runs
    winner = min(candidates, key=lambda run: (run["cost"], run["total_tokens"], run["elapsed_seconds"]))
    failed = [run for run in runs if run["termination_reason"] != "COMPLETED"]
    reason = (
        f"the other run(s) did not finish cleanly ({', '.join(run['termination_reason'] for run in failed)})"
        if failed and winner in clean_runs
        else "lowest cost among completed runs" if clean_runs
        else "lowest cost among runs that did not complete"
    )
    return {"winner": winner["system"], "reason": reason}


def _run_workflow_safely(workflow_name, runner, question):
    try:
        return runner(question, question_id="ui")
    except Exception:
        logger.exception("Workflow '%s' failed while comparing answers", workflow_name)
        return {
            "system": workflow_name,
            "question_id": "ui",
            "question": question,
            "answer": "This workflow failed. Check the backend terminal for the error details.",
            "iterations": 0,
            "tool_calls": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
            "elapsed_seconds": 0.0,
            "termination_reason": "ERROR",
            "trace_id": None,
        }


@app.post("/agentic/compare")
def agentic_compare(payload: CompareRequest):
    question = payload.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Please enter a question.")

    normal_result = _run_workflow_safely("normal_workflow", run_normal_workflow, question)
    agent_result = _run_workflow_safely("agent", run_agent, question)
    multi_agent_result = _run_workflow_safely("multi_agent", run_multi_agent, question)

    return {
        "question": question,
        "normal_workflow": _serialize_run(normal_result),
        "agent": _serialize_run(agent_result),
        "multi_agent": _serialize_run(multi_agent_result),
        "verdict": _pick_winner([normal_result, agent_result, multi_agent_result]),
    }
