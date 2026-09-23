import json
import shutil
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agentic_bridge import run_agent, run_workflow
from rag import retrieve_documents, generate_answer, GROQ_MODEL
from tracing import create_trace_id, save_trace
from vector_store import store_embeddings


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"
UPLOAD_DIR = BASE_DIR / "uploads"
STATUS_FILE = UPLOAD_DIR / "status.json"

UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="RAG Document Q&A")

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

    documents = retrieve_documents(question)

    if not documents:
        raise HTTPException(
            status_code=400,
            detail="No document content is available yet. Please upload a PDF.",
        )

     # Generate answer and capture metadata needed for tracing.
    answer, prompt, temperature = generate_answer(
        question,
        documents,
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
            {"tool": call["tool"], "arguments": call["arguments"]}
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


def _pick_winner(agent_result, workflow_result):
    """Efficiency-only comparison (completion, tokens, cost) -- this is
    NOT a correctness/accuracy judgment. Free-form UI questions have no
    ground-truth answer to grade against (unlike the fixed 10-question
    race in Agentic Ai/race_questions.json), so the UI must not claim to
    know which answer is more *correct*, only which run cost less."""

    agent_clean = agent_result["termination_reason"] == "COMPLETED"
    workflow_clean = workflow_result["termination_reason"] == "COMPLETED"

    if agent_clean != workflow_clean:
        winner = "agent" if agent_clean else "workflow"
        loser_reason = workflow_result if winner == "agent" else agent_result
        return {
            "winner": winner,
            "reason": f"the other run did not finish cleanly ({loser_reason['termination_reason']})",
        }

    if agent_result["cost"] != workflow_result["cost"]:
        winner = "agent" if agent_result["cost"] < workflow_result["cost"] else "workflow"
        return {"winner": winner, "reason": "lower cost for this question"}

    if agent_result["total_tokens"] != workflow_result["total_tokens"]:
        winner = "agent" if agent_result["total_tokens"] < workflow_result["total_tokens"] else "workflow"
        return {"winner": winner, "reason": "fewer total tokens for this question"}

    winner = "agent" if agent_result["elapsed_seconds"] < workflow_result["elapsed_seconds"] else "workflow"
    return {"winner": winner, "reason": "lower latency for this question"}


@app.post("/agentic/compare")
def agentic_compare(payload: CompareRequest):
    question = payload.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Please enter a question.")

    agent_result = run_agent(question, question_id="ui")
    workflow_result = run_workflow(question, question_id="ui")

    return {
        "question": question,
        "agent": _serialize_run(agent_result),
        "workflow": _serialize_run(workflow_result),
        "verdict": _pick_winner(agent_result, workflow_result),
    }
