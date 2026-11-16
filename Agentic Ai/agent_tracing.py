"""Trace saving for agent/workflow runs. Reuses src/tracing.py's trace-id
scheme and output/traces/ convention from the existing app; adds a run
schema that carries iterations, tool calls, per-call tokens/cost, and
termination reason, since that shape doesn't exist in the single-shot RAG
app's trace format.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

AGENTIC_DIR = Path(__file__).resolve().parent
BASE_DIR = AGENTIC_DIR.parent
SRC_DIR = BASE_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tracing import create_trace_id  # noqa: E402  (reused from src/tracing.py)
from redact import redact_obj  # noqa: E402

TRACE_DIR = AGENTIC_DIR / "output" / "traces"
TRACE_DIR.mkdir(parents=True, exist_ok=True)


def save_run_trace(
    system,
    question_id,
    question,
    iterations,
    tool_calls,
    llm_calls,
    total_input_tokens,
    total_output_tokens,
    total_tokens,
    total_cost,
    elapsed_seconds,
    termination_reason,
    final_answer,
    model,
    trace_id=None,
    extra=None,
):
    """`trace_id`: reuse the id minted at the entry point so one id spans every hop.
    `extra`: additional fields (group, evidence, spans) merged in after redaction.
    """
    trace_id = trace_id or create_trace_id()

    trace = {
        "trace_id": trace_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": system,  # "agent" or "workflow"
        "question_id": question_id,
        "question": question,
        "model": model,
        "iterations": iterations,
        "tool_calls": tool_calls,
        "llm_calls": llm_calls,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "elapsed_seconds": elapsed_seconds,
        "termination_reason": termination_reason,
        "final_answer": final_answer,
    }
    # Redact on write: questions can contain pasted keys, and the model may echo them into
    # tool arguments or the answer. `extra` is merged afterwards (it holds handbook text).
    trace = redact_obj(trace)
    trace.update(extra or {})

    trace_file = TRACE_DIR / f"{trace_id}.json"
    trace_file.write_text(
        json.dumps(trace, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return trace_id, trace_file
