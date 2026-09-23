"""Race the dynamic agent against the fixed workflow on the same 10
questions, same tools, same model, same output contract. Writes race.csv
and prints the aggregate comparison table.

Run directly: python race.py
"""

import csv
import json
import re
import statistics
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from agent import run_agent
from workflow import run_workflow

AGENTIC_DIR = Path(__file__).resolve().parent
QUESTIONS_FILE = AGENTIC_DIR / "race_questions.json"
OUTPUT_DIR = AGENTIC_DIR / "output"
RACE_CSV = OUTPUT_DIR / "race.csv"
RACE_SUMMARY = OUTPUT_DIR / "race_summary.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_questions():
    return json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))


_DASH_VARIANTS = "‐‑‒–—―"
_DASH_TRANSLATION = {ord(ch): "-" for ch in _DASH_VARIANTS}


def _normalize(text):
    """The model sometimes renders compound terms with a typographic
    non-breaking hyphen instead of ASCII '-', and routinely inserts
    non-breaking/narrow-no-break spaces (U+00A0, U+202F) between names,
    dates, and numbers instead of ASCII spaces (observed directly in this
    domain's race traces, e.g. "RAMESH\\u202fVAYAVURU"). Fold all of that
    to plain ASCII, and drop thousands-separator commas/spaces between
    digits (e.g. "1,000" / "1 000" -> "1000"), so substring matching isn't
    fooled by glyph or formatting choice."""
    text = (text or "").translate(_DASH_TRANSLATION)
    text = " ".join(text.split())  # collapses ALL Unicode whitespace, not just ASCII
    text = re.sub(r"(?<=\d)[,\s](?=\d)", "", text)
    return text.lower()


def evaluate(answer, spec):
    """Deterministic, substring-based pass/fail. See README "Pass/Fail
    Criteria" for the exact rule this implements."""

    text = _normalize(answer)
    missing_all = []
    for term in spec.get("must_contain", []):
        if term.lower() not in text:
            missing_all.append(term)

    any_ok = True
    any_group = spec.get("must_contain_any")
    if any_group:
        any_ok = any(term.lower() in text for term in any_group)

    min_ok = True
    min_matches = spec.get("min_matches_from")
    if min_matches:
        matched = [term for term in min_matches["list"] if term.lower() in text]
        min_ok = len(matched) >= min_matches["min"]

    passed = (not missing_all) and any_ok and min_ok

    return passed, {
        "missing_required": missing_all,
        "any_group_satisfied": any_ok,
        "min_matches_satisfied": min_ok,
    }


def run_race():
    questions = load_questions()

    rows = []
    per_system = {"agent": [], "workflow": []}

    for q in questions:
        for system_name, run_fn in (("agent", run_agent), ("workflow", run_workflow)):
            print(f"[race] {system_name} :: {q['id']}")
            result = run_fn(q["question"], question_id=q["id"])
            passed, eval_detail = evaluate(result["answer"], q)

            row = {
                "system": system_name,
                "question_id": q["id"],
                "passed": passed,
                "latency_ms": round(result["elapsed_seconds"] * 1000, 1),
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "total_tokens": result["total_tokens"],
                "cost": result["cost"],
                "termination_reason": result["termination_reason"],
            }
            rows.append(row)
            per_system[system_name].append(row)

            print(
                f"    passed={passed} latency_ms={row['latency_ms']} "
                f"total_tokens={row['total_tokens']} cost=${row['cost']:.6f} "
                f"termination={row['termination_reason']}"
            )
            if not passed:
                print(f"    missing/failed: {eval_detail}")

    with RACE_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "system",
                "question_id",
                "passed",
                "latency_ms",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "cost",
                "termination_reason",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    summary = {}
    for system_name, system_rows in per_system.items():
        n = len(system_rows)
        pass_rate = sum(1 for r in system_rows if r["passed"]) / n
        p50_latency_ms = statistics.median(r["latency_ms"] for r in system_rows)
        total_tokens = sum(r["total_tokens"] for r in system_rows)
        total_cost = sum(r["cost"] for r in system_rows)
        cost_per_question = total_cost / n

        summary[system_name] = {
            "pass_rate": pass_rate,
            "p50_latency_ms": p50_latency_ms,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "cost_per_question": cost_per_question,
        }

    RACE_SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=========== RACE RESULTS ===========")
    print(f"{'System':<10}{'Pass Rate':>12}{'p50 Latency':>15}{'Total Tokens':>15}{'Cost/Question':>16}")
    for system_name, s in summary.items():
        print(
            f"{system_name:<10}"
            f"{s['pass_rate'] * 100:>11.0f}%"
            f"{s['p50_latency_ms']:>13.0f}ms"
            f"{s['total_tokens']:>15}"
            f"{'$' + format(s['cost_per_question'], '.6f'):>16}"
        )

    print(f"\nWrote {RACE_CSV}")
    print(f"Wrote {RACE_SUMMARY}")

    return rows, summary


if __name__ == "__main__":
    run_race()
