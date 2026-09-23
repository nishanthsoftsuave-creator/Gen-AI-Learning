"""Controlled test that forces a REAL budget termination and saves the
actual log to output/budget_termination.log. Uses a deliberately tight
max_iterations=1 against a question that legitimately needs more than one
tool round-trip (Q3), so the agent completes one real iteration (with a
real tool call and real token usage), then is cleanly stopped before a
second LLM call would happen.

Run directly: python budget_termination_test.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from agent import run_agent
from budgets import BudgetTracker

AGENTIC_DIR = Path(__file__).resolve().parent
QUESTIONS_FILE = AGENTIC_DIR / "race_questions.json"
LOG_FILE = AGENTIC_DIR / "output" / "budget_termination.log"


def run_forced_termination():
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    question_spec = next(q for q in questions if q["id"] == "Q3")

    started_at = datetime.now(timezone.utc).isoformat()

    tight_tracker = BudgetTracker(max_iterations=1)
    result = run_agent(
        question_spec["question"],
        question_id="Q3-budget-test",
        budgets=tight_tracker,
        verbose=True,
    )

    lines = []
    lines.append("=== Budget Termination Test ===")
    lines.append(f"Question: {question_spec['question']}")
    lines.append(f"Started: {started_at}")
    lines.append(f"Configured budget: max_iterations=1 (all other budgets left at default)")
    lines.append("")

    for call in result["tool_calls"]:
        lines.append(f"Iteration: {call['iteration']}")
        lines.append(f"Tool: {call['tool']}")
        lines.append(f"Arguments: {call['arguments']}")
        lines.append("")

    for llm_call in tight_tracker.llm_calls:
        lines.append(f"LLM call (iteration {llm_call['iteration']}):")
        lines.append(f"  Input tokens: {llm_call['input_tokens']}")
        lines.append(f"  Output tokens: {llm_call['output_tokens']}")
        lines.append(f"  Cumulative tokens: {llm_call['cumulative_tokens']}")
        lines.append(f"  Cumulative cost: ${llm_call['cumulative_cost']:.6f}")
        lines.append("")

    lines.append(f"Total tokens: {result['total_tokens']}")
    lines.append(f"Elapsed seconds: {result['elapsed_seconds']:.3f}")
    lines.append(f"Cost: ${result['cost']:.6f}")
    lines.append("")
    lines.append(f"BUDGET TRIGGERED: {result['termination_reason']}")
    lines.append("ACTION: TERMINATE")
    lines.append(
        "STATUS: CLEAN_TERMINATION"
        if result["termination_reason"] != "COMPLETED"
        else "STATUS: COMPLETED_WITHOUT_TRIGGERING_A_BUDGET (test did not force a real trip -- rerun)"
    )
    lines.append("")
    lines.append(f"Final answer returned: {result['answer']}")
    lines.append(f"Trace file: {result['trace_file']}")

    log_text = "\n".join(lines)

    LOG_FILE.write_text(log_text, encoding="utf-8")

    print("\n" + log_text)
    print(f"\nWrote {LOG_FILE}")

    return result


if __name__ == "__main__":
    run_forced_termination()
