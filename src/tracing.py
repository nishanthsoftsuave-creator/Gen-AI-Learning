import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from redact import redact


BASE_DIR = Path(__file__).resolve().parent.parent
TRACE_DIR = BASE_DIR / "output" / "traces"

TRACE_DIR.mkdir(parents=True, exist_ok=True)

# rag_v1 -> v2: revision register + guard. v2 -> v3: policy figures only from context.
PROMPT_VERSION = "rag_v3"


def create_trace_id():
    return f"tr_{uuid.uuid4().hex[:12]}"


CATEGORY_KEYWORDS = {
    "revision-history": r"revision|revised",
    "leave": r"leave|holiday|vacation|sick",
    "payroll": r"salary|payroll|bonus|payslip|overtime",
    "benefits": r"insurance|benefit|reimburse|allowance",
    "conduct": r"conduct|harass|disciplin|dress code|ethic",
}


def classify_category(question):
    for category, pattern in CATEGORY_KEYWORDS.items():
        if re.search(pattern, question, re.I):
            return category
    return "other"


def build_spans(model, retrieval_seconds, usage):
    """Per-stage latency/tokens/cost; usage is rag.generate_answer's usage dict."""
    agentic_dir = str(BASE_DIR / "Agentic Ai")
    if agentic_dir not in sys.path:
        sys.path.insert(0, agentic_dir)
    from cost import calculate_cost

    tokens_in, tokens_out = usage["input_tokens"], usage["output_tokens"]
    return [
        {"name": "retrieval", "latency_seconds": retrieval_seconds,
         "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        {"name": "generation", "latency_seconds": usage["generation_seconds"],
         "input_tokens": tokens_in, "output_tokens": tokens_out,
         "cost_usd": calculate_cost(tokens_in, tokens_out, model=model)},
        {"name": "tools", "latency_seconds": 0.0,
         "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
    ]


def save_trace(
    trace_id,
    question,
    prompt,
    retrieved_chunks,
    model,
    temperature,
    raw_output,
    prompt_version=PROMPT_VERSION,
    user_ref=None,
    spans=None,
):
    trace = {
        "trace_id": trace_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),

        # slice fields: user and input type
        "user_ref": user_ref,
        "category": classify_category(question),

        "question": redact(question),

        "prompt_version": prompt_version,
        "prompt": redact(prompt),

        "retrieval": {
            "method": "hybrid",
            "top_k": len(retrieved_chunks),
            "chunks": retrieved_chunks,
        },

        "retrieved_context_ids": [chunk["chunk_id"] for chunk in retrieved_chunks],
        "retrieved_sources": sorted({chunk.get("source_file") or "unknown" for chunk in retrieved_chunks}),

        "model": model,
        "temperature": temperature,

        "spans": spans,
        "total_cost_usd": sum(s["cost_usd"] for s in spans) if spans else None,

        "raw_output": redact(raw_output),
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
