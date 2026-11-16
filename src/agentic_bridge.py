"""Bridge from the FastAPI app to the Week 7 Task Set E code in
`Agentic Ai/` (a sibling folder, not a Python package -- its name has a
space, so it can't be dotted-imported). Adding its directory to sys.path
lets its own internal top-level imports (`from budgets import ...` etc.)
resolve exactly as they do when those scripts are run directly.
"""

import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
AGENTIC_DIR = BASE_DIR / "Agentic Ai"

if str(AGENTIC_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTIC_DIR))

from agent import run_agent  # noqa: E402
from multi_agent import run_multi_agent  # noqa: E402
from rag import GROQ_MODEL, generate_answer, retrieve_documents  # noqa: E402
from tracing import build_spans, create_trace_id, save_trace  # noqa: E402
from agent_tracing import save_run_trace  # noqa: E402
from cost import calculate_cost  # noqa: E402


def run_normal_workflow(question, question_id="adhoc"):
    """Run the same hybrid retrieval and answer generation used by /ask."""
    started = time.monotonic()
    retrieval_started = time.monotonic()
    documents = retrieve_documents(question)
    retrieval_seconds = time.monotonic() - retrieval_started
    if not documents:
        answer = "No indexed document content was found. Upload a PDF in Document Q&A first."
        usage = {"input_tokens": 0, "output_tokens": 0, "generation_seconds": 0.0}
        prompt = ""
        temperature = 0.3
        termination_reason = "NO_DOCUMENTS"
    else:
        answer, prompt, temperature, usage = generate_answer(
            question, documents, include_usage=True
        )
        termination_reason = "COMPLETED"

    trace_id = create_trace_id()
    save_trace(
        trace_id=trace_id,
        question=question,
        prompt=prompt,
        retrieved_chunks=documents,
        model=GROQ_MODEL,
        temperature=temperature,
        raw_output=answer,
        spans=build_spans(GROQ_MODEL, retrieval_seconds, usage),
    )
    total_tokens = usage["input_tokens"] + usage["output_tokens"]
    cost = calculate_cost(
        usage["input_tokens"], usage["output_tokens"], model=GROQ_MODEL
    )
    trace_id, trace_file = save_run_trace(
        system="normal_workflow",
        question_id=question_id,
        question=question,
        iterations=1 if documents else 0,
        tool_calls=[],
        llm_calls=[usage] if documents else [],
        total_input_tokens=usage["input_tokens"],
        total_output_tokens=usage["output_tokens"],
        total_tokens=total_tokens,
        total_cost=cost,
        elapsed_seconds=time.monotonic() - started,
        termination_reason=termination_reason,
        final_answer=answer,
        model=GROQ_MODEL,
    )
    return {
        "system": "normal_workflow",
        "question_id": question_id,
        "question": question,
        "answer": answer,
        "iterations": 1 if documents else 0,
        "tool_calls": [],
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "total_tokens": total_tokens,
        "cost": cost,
        "elapsed_seconds": time.monotonic() - started,
        "termination_reason": termination_reason,
        "trace_id": trace_id,
        "trace_file": str(trace_file),
    }


__all__ = ["run_agent", "run_normal_workflow", "run_multi_agent"]
