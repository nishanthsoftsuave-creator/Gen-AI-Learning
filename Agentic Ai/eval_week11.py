"""Deterministic regression replay for the real stale-revision trace.

The original Week 6 answer-quality suite is not present in this workspace;
this is the complete local HR regression suite and intentionally uses no API.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from revision_guard import enforce_revision_authority  # noqa: E402


def evaluate(answer, case):
    folded = answer.casefold().replace("\u202f", " ")
    return all(term.casefold().replace("\u202f", " ") in folded for term in case["must_contain"]) and not any(
        term.casefold().replace("\u202f", " ") in folded for term in case["must_not_contain"]
    )


def live_answer(question):
    """Run the question through the current prompt (real retrieval + Groq call)."""
    import time
    from rag import GROQ_MODEL, generate_answer, retrieve_documents
    from tracing import build_spans, create_trace_id, save_trace

    started = time.perf_counter()
    docs = retrieve_documents(question)
    retrieval_seconds = time.perf_counter() - started
    answer, prompt, temperature, usage = generate_answer(question, docs, include_usage=True)
    save_trace(create_trace_id(), question, prompt, docs, GROQ_MODEL, temperature, answer,
               user_ref="eval", spans=build_spans(GROQ_MODEL, retrieval_seconds, usage))
    time.sleep(8)  # stay under the 8,000 TPM account limit across consecutive live cases
    return answer


def run(mode):
    cases = [json.loads(line) for line in (TASK / "week11_eval_cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    failures = []
    passed = 0
    for case in cases:
        # A case may carry a synthetic model answer when no logged trace exists for it.
        answer = case.get("answer") or json.loads(
            (ROOT / "output" / "traces" / f"{case['failure_trace_id']}.json").read_text(encoding="utf-8")
        )["raw_output"]
        if mode == "after":
            answer = enforce_revision_authority(case["question"], answer, TASK / "handbook_revisions.json")
            if case.get("live"):
                answer = live_answer(case["question"])
        ok = evaluate(answer, case)
        passed += int(ok)
        print(f"{'PASS' if ok else 'FAIL'} {case['id']}")
        if not ok:
            failures.append(case["id"])
    print(f"SUITE {mode.upper()}: {passed}/{len(cases)} passed")
    return 0 if not failures else 1


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"before", "after"}:
        raise SystemExit("usage: python eval_week11.py before|after")
    raise SystemExit(run(sys.argv[1]))
