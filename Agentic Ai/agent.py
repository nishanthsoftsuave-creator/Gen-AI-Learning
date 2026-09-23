"""Dynamic agent loop: the LLM decides which of the 3 tools to call next
based on what the previous tool call returned, until it produces a final
answer or one of the four budgets fires.

Run directly: python agent.py
Run one question non-interactively: python agent.py --question "..."
"""

import argparse
import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

from budgets import BudgetTracker, TERMINATION_COMPLETED
from llm_client import chat, GROQ_MODEL
from tools import TOOL_SCHEMAS, dispatch_tool, ToolError
from agent_tracing import save_run_trace

SYSTEM_PROMPT = """You are an HR-support assistant for the Soft Suave Employee Handbook. Answer the employee's question about company policy.

You have three tools:
- search_handbook: narrative search across the Handbook for a natural-language question.
- get_policy_section: full, verbatim text of ONE specific, named policy section.
- get_handbook_revisions: the Handbook document's own dated revision history and modifications clause (NOT policy content).

Call whichever tools you need, in whatever order the question requires -- a question may need only one tool, or may need you to inspect one tool's result before deciding which tool to call next. Do not guess at names, dates, amounts, or contacts -- look them up.

Be efficient: prefer get_policy_section when the question names or clearly implies one specific section, and get_handbook_revisions when the question is about how many times or when the Handbook itself was updated -- both return exact data in a single call, faster than searching for it. Read each tool result carefully before calling another tool: if what you already retrieved answers the question, answer immediately instead of searching again. Never repeat a tool call with a near-identical query or argument you already tried.

When you have enough information, respond with a final answer in plain text (no more tool calls). Cite concrete names, dates, amounts, and email addresses from the tool results in your answer -- don't paraphrase away the specifics."""


def _message_to_dict(message):
    entry = {"role": "assistant", "content": message.content or ""}
    if message.tool_calls:
        entry["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in message.tool_calls
        ]
    return entry


def run_agent(question, question_id="adhoc", budgets=None, verbose=False):
    tracker = budgets or BudgetTracker()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    tool_call_log = []
    final_answer = None
    termination_reason = TERMINATION_COMPLETED

    while True:
        tracker.begin_iteration()

        reason = tracker.check()
        if reason:
            termination_reason = reason
            if verbose:
                print(f"[Budget] TRIGGERED before iteration {tracker.iterations}: {reason}")
            break

        message, usage = chat(messages, tools=TOOL_SCHEMAS, tool_choice="auto")
        tracker.record_llm_call(usage["input_tokens"], usage["output_tokens"], GROQ_MODEL)

        if verbose:
            print(
                f"[Agent] iteration={tracker.iterations} "
                f"input_tokens={usage['input_tokens']} output_tokens={usage['output_tokens']} "
                f"cumulative_tokens={tracker.total_tokens} cumulative_cost={tracker.total_cost:.6f}"
            )

        reason = tracker.check()
        if reason:
            termination_reason = reason
            if verbose:
                print(f"[Budget] TRIGGERED after LLM call {tracker.iterations}: {reason}")
            break

        messages.append(_message_to_dict(message))

        if message.tool_calls:
            for tool_call in message.tool_calls:
                name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}

                try:
                    result = dispatch_tool(name, arguments)
                    error = None
                except ToolError as exc:
                    result = {"error": str(exc)}
                    error = str(exc)

                tool_call_log.append(
                    {
                        "iteration": tracker.iterations,
                        "tool": name,
                        "arguments": arguments,
                        "error": error,
                    }
                )

                if verbose:
                    print(f"[Tool] {name}({arguments}) -> {'ERROR: ' + error if error else 'ok'}")

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            continue

        final_answer = message.content
        break

    if final_answer is None and termination_reason != TERMINATION_COMPLETED:
        final_answer = (
            f"[No final answer -- agent terminated early due to {termination_reason}]"
        )

    snapshot = tracker.snapshot()

    trace_id, trace_file = save_run_trace(
        system="agent",
        question_id=question_id,
        question=question,
        iterations=snapshot["iterations"],
        tool_calls=tool_call_log,
        llm_calls=tracker.llm_calls,
        total_input_tokens=snapshot["total_input_tokens"],
        total_output_tokens=snapshot["total_output_tokens"],
        total_tokens=snapshot["total_tokens"],
        total_cost=snapshot["total_cost"],
        elapsed_seconds=snapshot["elapsed_seconds"],
        termination_reason=termination_reason,
        final_answer=final_answer,
        model=GROQ_MODEL,
    )

    return {
        "system": "agent",
        "question_id": question_id,
        "question": question,
        "answer": final_answer,
        "iterations": snapshot["iterations"],
        "tool_calls": tool_call_log,
        "input_tokens": snapshot["total_input_tokens"],
        "output_tokens": snapshot["total_output_tokens"],
        "total_tokens": snapshot["total_tokens"],
        "cost": snapshot["total_cost"],
        "elapsed_seconds": snapshot["elapsed_seconds"],
        "termination_reason": termination_reason,
        "trace_id": trace_id,
        "trace_file": str(trace_file),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the dynamic Employee Handbook agent.")
    parser.add_argument("--question", help="Ask a single question and exit.")
    args = parser.parse_args()

    if args.question:
        result = run_agent(args.question, verbose=True)
        print("\n========== ANSWER ==========")
        print(result["answer"])
        print(f"\nTermination: {result['termination_reason']}")
        print(f"Iterations: {result['iterations']}")
        print(f"Total tokens: {result['total_tokens']}  Cost: ${result['cost']:.6f}")
        print(f"Elapsed: {result['elapsed_seconds']:.2f}s")
        print(f"Trace: {result['trace_file']}")
    else:
        while True:
            question = input("Ask about the Employee Handbook (or 'exit'): ")
            if question.strip().lower() == "exit":
                break

            start = time.monotonic()
            result = run_agent(question, verbose=True)

            print("\n========== ANSWER ==========")
            print(result["answer"])
            print(f"\nTermination: {result['termination_reason']}")
            print(f"Iterations: {result['iterations']}")
            print(f"Total tokens: {result['total_tokens']}  Cost: ${result['cost']:.6f}")
            print(f"Elapsed: {result['elapsed_seconds']:.2f}s")
            print(f"Trace: {result['trace_file']}\n")
