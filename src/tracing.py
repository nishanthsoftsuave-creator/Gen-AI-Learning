import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
TRACE_DIR = BASE_DIR / "output" / "traces"

TRACE_DIR.mkdir(parents=True, exist_ok=True)


def create_trace_id():
    return f"tr_{uuid.uuid4().hex[:12]}"


def save_trace(
    trace_id,
    question,
    prompt,
    retrieved_chunks,
    model,
    temperature,
    raw_output,
    prompt_version="rag_v1",
):
    trace = {
        "trace_id": trace_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),

        "question": question,

        "prompt_version": prompt_version,
        "prompt": prompt,

        "retrieval": {
            "method": "hybrid",
            "top_k": len(retrieved_chunks),
            "chunks": retrieved_chunks,
        },

        "model": model,
        "temperature": temperature,

        "raw_output": raw_output,
    }

    trace_file = TRACE_DIR / f"{trace_id}.json"

    trace_file.write_text(
        json.dumps(
            trace,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return trace_file