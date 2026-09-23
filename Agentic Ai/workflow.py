"""Fixed workflow: the SAME tools, SAME model, SAME 10 questions, SAME
output contract as agent.py -- but with a hard-coded step sequence. No tool
choice is ever made based on a previous tool's result: every question
always triggers search_handbook once, get_policy_section once for EVERY
known section, and get_handbook_revisions once, then exactly one LLM call
synthesizes the final answer from whatever those fixed calls returned.

Budgets (max iterations/tokens/cost/wall-clock) are an agent-loop concept --
this pipeline has no loop to bound, so it isn't subject to them. Token/cost/
latency are still measured for the race.

Run directly: python workflow.py
Run one question non-interactively: python workflow.py --question "..."
"""

import argparse
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from budgets import BudgetTracker, TERMINATION_COMPLETED
from llm_client import chat, GROQ_MODEL
from tools import search_handbook, get_policy_section, get_handbook_revisions, SUPPORTED_SECTIONS
from agent_tracing import save_run_trace

GENERATION_PROMPT_TEMPLATE = """You are an HR-support assistant for the Soft \
Suave Employee Handbook. Answer the question using ONLY the reference \
material below. Cite concrete names, dates, amounts, and email addresses \
from it -- don't paraphrase away the specifics.

## Handbook search results
{docs}

## All policy sections (verbatim)
{sections}

## Handbook revision history
{revisions}

## Question
{question}

## Answer
"""


def _fixed_tool_steps(question):
    """Hard-coded step sequence -- identical for every question, regardless
    of content. This is the entire "workflow": no branching, no loop."""

    docs = search_handbook(query=question, top_k=4)
    sections = {section: get_policy_section(section=section) for section in SUPPORTED_SECTIONS}
    revisions = get_handbook_revisions()

    tool_calls = [
        {"iteration": 1, "tool": "search_handbook", "arguments": {"query": question, "top_k": 4}, "error": None},
    ]
    for section in SUPPORTED_SECTIONS:
        tool_calls.append(
            {"iteration": 1, "tool": "get_policy_section", "arguments": {"section": section}, "error": None}
        )
    tool_calls.append({"iteration": 1, "tool": "get_handbook_revisions", "arguments": {}, "error": None})

    return docs, sections, revisions, tool_calls


def run_workflow(question, question_id="adhoc", verbose=False):
    tracker = BudgetTracker()  # used only for token/cost bookkeeping here
    tracker.begin_iteration()

    docs, sections, revisions, tool_calls = _fixed_tool_steps(question)

    prompt = GENERATION_PROMPT_TEMPLATE.format(
        docs=json.dumps(docs, indent=2, ensure_ascii=False),
        sections=json.dumps(sections, indent=2, ensure_ascii=False),
        revisions=json.dumps(revisions, indent=2, ensure_ascii=False),
        question=question,
    )

    message, usage = chat([{"role": "user", "content": prompt}], tools=None)
    tracker.record_llm_call(usage["input_tokens"], usage["output_tokens"], GROQ_MODEL)

    if verbose:
        print(
            f"[Workflow] input_tokens={usage['input_tokens']} "
            f"output_tokens={usage['output_tokens']} cost={tracker.total_cost:.6f}"
        )

    answer = message.content
    snapshot = tracker.snapshot()

    trace_id, trace_file = save_run_trace(
        system="workflow",
        question_id=question_id,
        question=question,
        iterations=1,
        tool_calls=tool_calls,
        llm_calls=tracker.llm_calls,
        total_input_tokens=snapshot["total_input_tokens"],
        total_output_tokens=snapshot["total_output_tokens"],
        total_tokens=snapshot["total_tokens"],
        total_cost=snapshot["total_cost"],
        elapsed_seconds=snapshot["elapsed_seconds"],
        termination_reason=TERMINATION_COMPLETED,
        final_answer=answer,
        model=GROQ_MODEL,
    )

    return {
        "system": "workflow",
        "question_id": question_id,
        "question": question,
        "answer": answer,
        "iterations": 1,
        "tool_calls": tool_calls,
        "input_tokens": snapshot["total_input_tokens"],
        "output_tokens": snapshot["total_output_tokens"],
        "total_tokens": snapshot["total_tokens"],
        "cost": snapshot["total_cost"],
        "elapsed_seconds": snapshot["elapsed_seconds"],
        "termination_reason": TERMINATION_COMPLETED,
        "trace_id": trace_id,
        "trace_file": str(trace_file),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the fixed Employee Handbook workflow.")
    parser.add_argument("--question", help="Ask a single question and exit.")
    args = parser.parse_args()

    if args.question:
        result = run_workflow(args.question, verbose=True)
        print("\n========== ANSWER ==========")
        print(result["answer"])
        print(f"\nTotal tokens: {result['total_tokens']}  Cost: ${result['cost']:.6f}")
        print(f"Elapsed: {result['elapsed_seconds']:.2f}s")
        print(f"Trace: {result['trace_file']}")
    else:
        while True:
            question = input("Ask about the Employee Handbook (fixed workflow, or 'exit'): ")
            if question.strip().lower() == "exit":
                break

            result = run_workflow(question, verbose=True)

            print("\n========== ANSWER ==========")
            print(result["answer"])
            print(f"\nTotal tokens: {result['total_tokens']}  Cost: ${result['cost']:.6f}")
            print(f"Elapsed: {result['elapsed_seconds']:.2f}s")
            print(f"Trace: {result['trace_file']}\n")
