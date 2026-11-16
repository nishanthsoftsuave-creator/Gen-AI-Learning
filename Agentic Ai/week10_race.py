"""Run the unchanged HR question set against the single agent and orchestrator.

Outputs live in output/week10_hr_handbook/. Percentiles use the nearest-rank
definition, so p99 for ten observations is the maximum observed latency.
"""

import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
OUT = HERE
RACE_JSON = OUT / "race_results.json"

from agent import run_agent
from orchestrator import run_orchestrator
from race import QUESTIONS_FILE, evaluate

AGENT_CARD = {
    "name": "Soft Suave HR Handbook Orchestrator",
    "description": (
        "Coordinates handbook policy-content and document revision-history workers."
    ),
    "url": "http://127.0.0.1:8000/a2a",
    "version": "1.0.0",
    "protocolVersion": "1.0.0",
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
        "stateTransitionHistory": False,
    },
    "defaultInputModes": ["text/plain", "application/json"],
    "defaultOutputModes": ["text/plain", "application/json"],
    "securitySchemes": {},
    "skills": [
        {
            "id": "handbook-policy-content",
            "name": "Handbook policy and procedure lookup",
            "description": "Find and explain policy text, procedures, contacts, and consequences from the Employee Handbook.",
            "tags": ["HR", "handbook", "policy", "procedure"],
            "examples": ["What are the disciplinary consequences in the Handbook?"],
            "inputModes": ["text/plain"],
            "outputModes": ["text/plain", "application/json"],
        },
        {
            "id": "handbook-revision-history",
            "name": "Handbook document revision history",
            "description": "Return the Handbook document's revision count, dates, and modification clause.",
            "tags": ["HR", "handbook", "revision history"],
            "examples": ["When was the latest Handbook revision?"],
            "inputModes": ["text/plain"],
            "outputModes": ["text/plain", "application/json"],
        },
    ],
}


def _nearest_rank(values, percentile):
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def _summarize(rows, system):
    selected = [row for row in rows if row["system"] == system]
    count = len(selected)
    costs = sum(row["cost"] for row in selected)
    return {
        "case_count": count,
        "pass_count": sum(row["passed"] for row in selected),
        "pass_rate": sum(row["passed"] for row in selected) / count,
        "p50_latency_ms": statistics.median(row["latency_ms"] for row in selected),
        "p99_latency_ms": _nearest_rank([row["latency_ms"] for row in selected], 0.99),
        "total_tokens": sum(row["total_tokens"] for row in selected),
        "total_cost": costs,
        "cost_per_question": costs / count,
    }


def _write_race_table(rows, single, multi, question_hash):
    names = ", ".join(row["question_id"] for row in rows if row["system"] == "agent")
    content = f"""# Week 10 HR Handbook Race

The exact existing `race_questions.json` file was used unchanged. It is the
repo's Week 7 HR set; no separate Week 6 HR evaluation file exists here.
Cases: {names}. SHA-256 of source set: `{question_hash}`.

Latency percentiles use nearest rank (for 10 cases, p99 is the maximum).

| Metric | Single agent | HR specialist orchestrator |
|---|---:|---:|
| Pass rate | {single['pass_count']}/{single['case_count']} ({single['pass_rate']:.0%}) | {multi['pass_count']}/{multi['case_count']} ({multi['pass_rate']:.0%}) |
| Latency p50 / p99 | {single['p50_latency_ms']:.1f} / {single['p99_latency_ms']:.1f} ms | {multi['p50_latency_ms']:.1f} / {multi['p99_latency_ms']:.1f} ms |
| Total tokens | {single['total_tokens']:,} | {multi['total_tokens']:,} |
| Cost per question | ${single['cost_per_question']:.6f} | ${multi['cost_per_question']:.6f} |

Totals: single-agent ${single['total_cost']:.6f}; orchestrator ${multi['total_cost']:.6f}.
"""
    (OUT / "race_table.md").write_text(content, encoding="utf-8")


def _write_handoffs(orchestrator_results, single_tokens, multi_tokens):
    buckets = {}
    lines = [
        "Per-call LLM usage for all normal orchestrator race cases. Logs contain",
        "worker role and token counts only; no user question or retrieved text.",
        "",
    ]
    for result in orchestrator_results:
        for call in result["llm_calls"]:
            name = call["handoff"]
            tokens = call["total_tokens"]
            lines.append(
                f"{result['question_id']} | {name} | input={call['input_tokens']} "
                f"output={call['output_tokens']} total={tokens}"
            )
            if " -> " in name:
                buckets[name] = buckets.get(name, 0) + tokens

    dominant_name, dominant_tokens = max(
        buckets.items(), key=lambda pair: pair[1], default=("no worker hand-offs recorded", 0)
    )
    share = dominant_tokens / multi_tokens if multi_tokens else 0
    multiplier = multi_tokens / single_tokens if single_tokens else float("inf")
    lines.extend([
        "",
        f"Context re-send multiplier (orchestrator total / single-agent total): {multiplier:.1f}x.",
        f"Largest worker hand-off: {dominant_name}, {dominant_tokens:,} tokens "
        f"({share:.1%} of orchestrator tokens; summed from the per-call lines above).",
    ])
    (OUT / "handoffs.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return multiplier, dominant_name, dominant_tokens, share


def _write_failure_case(question):
    outcome = run_orchestrator(
        question["question"],
        question_id=question["id"] + "-INJECTED-500",
        inject_worker_500="policy-content",
    )
    passed, detail = evaluate(outcome["answer"], question)
    failures = [call for call in outcome["tool_calls"] if call.get("error")]
    policy_delegations = [
        call for call in outcome["tool_calls"] if call.get("worker") == "policy-content"
    ]
    if len(policy_delegations) > 1 and any(call.get("error") for call in policy_delegations):
        behavior = "The orchestrator retried the policy-content worker after the injected 500."
    elif passed:
        behavior = (
            "The answer passed the substring judge after the injected 500. This does not "
            "prove grounded recovery; confirm a successful policy-content result in the "
            "recorded calls before treating it as verified."
        )
    else:
        behavior = "The orchestrator degraded to a partial answer; the unchanged judge marked it failed."
    if any("500" in str(call["error"]) for call in failures):
        observed = "Injected policy-content worker HTTP 500 was returned to the orchestrator."
    else:
        observed = "No 500 hand-off was recorded; the intended worker hand-off did not occur."
    content = f"""# Injected Worker Failure

Case: {question['id']} (existing unchanged HR evaluation case).
Worker: policy-content specialist (the narrow worker that searches handbook
policy text). Injection: one synthetic HTTP 500 at its hand-off.

{observed}
Observed behavior: {behavior} No automatic retry was added by the worker
adapter; the orchestrator received the error and decided what to do next.

Outcome evaluator: {'PASS' if passed else 'FAIL'}; details: `{json.dumps(detail)}`.
**A2A mapping:** with no usable fallback, this input is sufficient so the task should end `failed`, not `input-required`; asking the user cannot fix a worker outage.
**A2A over plain REST:** A2A standardizes AgentCard/skill discovery and task status such as `working`, `input-required`, and `failed`. A plain REST worker call needs custom conventions for discovery, progress, and recovery.
Run answer:

> {outcome['answer'].replace(chr(10), chr(10) + '> ')}

Recorded orchestration calls: `{json.dumps(outcome['tool_calls'], ensure_ascii=False)}`.
"""
    (OUT / "failure_case.md").write_text(content, encoding="utf-8")
    return outcome, passed


def _write_verdict(single, multi):
    token_multiplier = multi["total_tokens"] / single["total_tokens"]
    cost_multiplier = multi["cost_per_question"] / single["cost_per_question"]
    # Predeclared gate: require an accuracy improvement and cap the bill at 2x.
    keep = multi["pass_rate"] > single["pass_rate"] and cost_multiplier <= 2.0
    decision = "KEEP" if keep else "KILL"
    reason = (
        "It improved pass rate while staying within the 2x cost ceiling."
        if keep else
        "It did not improve pass rate within the predeclared 2x cost ceiling."
    )
    content = f"""# Verdict: {decision}

Sunk-cost bias named: prior effort building the orchestrator does not count as evidence.
{reason}
Pass rate: single {single['pass_count']}/{single['case_count']} ({single['pass_rate']:.0%}); orchestrator {multi['pass_count']}/{multi['case_count']} ({multi['pass_rate']:.0%}).
Tokens: single {single['total_tokens']:,}; orchestrator {multi['total_tokens']:,} ({token_multiplier:.1f}x).
Cost/question: single ${single['cost_per_question']:.6f}; orchestrator ${multi['cost_per_question']:.6f} ({cost_multiplier:.1f}x).
Decision gate: keep only for higher pass rate and at most 2x cost per question.
"""
    (OUT / "verdict.md").write_text(content, encoding="utf-8")


def run_race():
    (OUT / "agentcard.json").write_text(
        json.dumps(AGENT_CARD, indent=2), encoding="utf-8"
    )
    (OUT / "agentcard_note.md").write_text(
        "This is proposed A2A AgentCard metadata for the HR orchestrator. "
        "The current implementation uses local MCP stdio and does not host "
        "the advertised HTTP A2A endpoint yet. No authentication is configured "
        "for this local exercise.\n",
        encoding="utf-8",
    )
    question_bytes = QUESTIONS_FILE.read_bytes()
    questions = json.loads(question_bytes)
    question_hash = hashlib.sha256(question_bytes).hexdigest()
    rows = []
    orchestrator_results = []

    for index, question in enumerate(questions):
        arms = (
            (("agent", run_agent), ("orchestrator", run_orchestrator))
            if index % 2 == 0 else
            (("orchestrator", run_orchestrator), ("agent", run_agent))
        )
        for system, function in arms:
            print(f"[week10] {system} {question['id']}", flush=True)
            result = function(question["question"], question_id=question["id"])
            passed, detail = evaluate(result["answer"], question)
            row = {
                "system": system,
                "question_id": question["id"],
                "passed": passed,
                "latency_ms": round(result["elapsed_seconds"] * 1000, 1),
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "total_tokens": result["total_tokens"],
                "cost": result["cost"],
                "termination_reason": result["termination_reason"],
            }
            rows.append(row)
            if system == "orchestrator":
                orchestrator_results.append(result)
            RACE_JSON.write_text(json.dumps(rows, indent=2), encoding="utf-8")
            print(
                f"  pass={passed} tokens={row['total_tokens']} "
                f"cost=${row['cost']:.6f} latency_ms={row['latency_ms']}",
                flush=True,
            )

    single = _summarize(rows, "agent")
    multi = _summarize(rows, "orchestrator")
    _write_race_table(rows, single, multi, question_hash)
    _write_verdict(single, multi)
    multiplier, dominant, handoff_tokens, share = _write_handoffs(
        orchestrator_results, single["total_tokens"], multi["total_tokens"]
    )

    # Inject one isolated failure after the measured race so its usage does not
    # contaminate either arm's reported token or cost totals.
    failure_case = next(q for q in questions if q["id"] == "Q7")
    failure_result, failure_passed = _write_failure_case(failure_case)

    print("\nRace complete:")
    print(json.dumps({"single_agent": single, "orchestrator": multi}, indent=2))
    print(
        f"multiplier={multiplier:.1f}x; dominant handoff={dominant} "
        f"({handoff_tokens:,} tokens, {share:.1%}); "
        f"failure Q7 pass={failure_passed}; answer_tokens={failure_result['total_tokens']}"
    )
    print(f"Artifacts: {OUT}")
    return rows, single, multi


if __name__ == "__main__":
    run_race()
