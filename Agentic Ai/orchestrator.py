"""HR Handbook orchestrator with two narrowly scoped specialist workers.

The policy-content worker can search/retrieve handbook sections. The
revision-history worker can retrieve the Handbook's own revision history.
Both use the MCP-discovered tools; the orchestrator delegates and synthesizes
but never changes the single-agent path.
"""

import argparse
import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

from agent_tracing import save_run_trace
from budgets import TERMINATION_COMPLETED
from llm_client import GROQ_MODEL, chat
from tools import TOOL_SCHEMAS, ToolError, dispatch_tool

POLICY_TOOLS = {"search_handbook", "get_policy_section"}
REVISION_TOOLS = {"get_handbook_revisions"}

ORCHESTRATOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "delegate_policy_content",
            "description": (
                "Delegate a focused Employee Handbook policy-content question "
                "to the policy-content specialist. Use for policy wording, "
                "procedures, contacts, leadership, and disciplinary matters."
            ),
            "parameters": {
                "type": "object",
                "properties": {"task": {"type": "string"}},
                "required": ["task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_revision_history",
            "description": (
                "Delegate questions about the Employee Handbook document's "
                "revision count, dates, or modification history to the "
                "revision-history specialist."
            ),
            "parameters": {
                "type": "object",
                "properties": {"task": {"type": "string"}},
                "required": ["task"],
            },
        },
    },
]

ORCHESTRATOR_PROMPT = """You coordinate two HR Handbook specialists.
Delegate each fact-finding task to the appropriate specialist:
- policy-content specialist: handbook policies, procedures, names, contacts,
  and consequences.
- revision-history specialist: the Handbook document's dated revision list.
Use both when a question needs both kinds of facts. Synthesize only facts
supported by worker results. If a worker fails and no other worker can verify
the missing fact, say that part could not be verified; do not guess."""

WORKER_PROMPTS = {
    "policy-content": (
        "You are the Soft Suave Employee Handbook policy-content specialist. "
        "Use only your available handbook tools. Return concise sourced facts "
        "and identify anything you could not verify. Do not invent details."
    ),
    "revision-history": (
        "You are the Employee Handbook document revision-history specialist. "
        "Use the available revision-history tool and report the exact revision "
        "count, dates, and modification clause relevant to the task. Do not "
        "confuse document revisions with policy versions."
    ),
}


class InjectedWorkerHTTPError(RuntimeError):
    """Synthetic worker gateway failure used only by the failure exercise."""


def _tool_schemas_for(names):
    return [
        schema for schema in TOOL_SCHEMAS
        if schema.get("function", {}).get("name") in names
    ]


def _tool_call_dict(message):
    return [
        {
            "id": item.id,
            "type": "function",
            "function": {
                "name": item.function.name,
                "arguments": item.function.arguments,
            },
        }
        for item in (message.tool_calls or [])
    ]


def _run_worker(worker, task, usage_log, tool_log, failure_state):
    """Run one specialist with only its own MCP tools and account usage."""
    if worker == failure_state.get("inject_worker_500"):
        failure_state["inject_worker_500"] = None
        raise InjectedWorkerHTTPError("injected worker gateway HTTP 500")

    allowed = REVISION_TOOLS if worker == "revision-history" else POLICY_TOOLS
    schemas = _tool_schemas_for(allowed)
    messages = [
        {"role": "system", "content": WORKER_PROMPTS[worker]},
        {"role": "user", "content": task},
    ]
    for worker_iteration in range(1, 5):
        message, usage = chat(messages, tools=schemas, tool_choice="auto")
        usage_log.append({
            "handoff": f"orchestrator -> {worker} worker",
            "worker_iteration": worker_iteration,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "total_tokens": usage["total_tokens"],
        })
        if not message.tool_calls:
            return message.content or "The worker returned no verified findings."

        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": _tool_call_dict(message),
        })
        for call in message.tool_calls:
            name = call.function.name
            arguments = {}
            try:
                arguments = json.loads(call.function.arguments or "{}")
                if name not in allowed:
                    raise ToolError(f"Tool '{name}' is outside the {worker} worker scope.")
                result = dispatch_tool(name, arguments)
                error = None
            except (ToolError, json.JSONDecodeError) as exc:
                result = {"error": str(exc)}
                error = str(exc)
            tool_log.append({
                "worker": worker,
                "tool": name,
                "arguments": arguments,
                "error": error,
            })
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
    return "The worker reached its four-call limit before producing findings."


def run_orchestrator(question, question_id="adhoc", inject_worker_500=None):
    """Delegate to specialists, synthesize a final answer, and record usage.

    ``inject_worker_500`` names a specialist for a one-shot synthetic HTTP
    500, used only by the Week 10 failure exercise. It does not alter normal
    race runs.
    """
    started = time.monotonic()
    usage_log = []
    tool_log = []
    messages = [
        {"role": "system", "content": ORCHESTRATOR_PROMPT},
        {"role": "user", "content": question},
    ]
    failure_state = {"inject_worker_500": inject_worker_500}

    for iteration in range(1, 9):
        tool_choice = "required" if inject_worker_500 and iteration == 1 else "auto"
        message, usage = chat(messages, tools=ORCHESTRATOR_TOOLS, tool_choice=tool_choice)
        usage_log.append({
            "handoff": "orchestrator planning/synthesis",
            "iteration": iteration,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "total_tokens": usage["total_tokens"],
        })
        if not message.tool_calls:
            answer = message.content or "I could not verify an answer from the handbook."
            break

        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": _tool_call_dict(message),
        })
        for call in message.tool_calls:
            name = call.function.name
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            worker = (
                "revision-history" if name == "delegate_revision_history"
                else "policy-content"
            )
            source = "orchestrator -> revision-history worker" if worker == "revision-history" else "orchestrator -> policy-content worker"
            try:
                if name not in {"delegate_policy_content", "delegate_revision_history"}:
                    raise ValueError(f"Unknown delegation '{name}'.")
                result = _run_worker(worker, arguments.get("task", question), usage_log, tool_log, failure_state)
                handoff_error = None
            except InjectedWorkerHTTPError as exc:
                result = {"worker": worker, "status": 500, "error": str(exc)}
                handoff_error = str(exc)
                usage_log.append({
                    "handoff": source,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "error": "injected HTTP 500",
                })
            tool_log.append({
                "iteration": iteration,
                "tool": name,
                "worker": worker,
                "task": arguments.get("task", ""),
                "error": handoff_error,
            })
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
    else:
        answer = "I could not complete a verified answer within the orchestration limit."

    elapsed = time.monotonic() - started
    total_input = sum(call["input_tokens"] for call in usage_log)
    total_output = sum(call["output_tokens"] for call in usage_log)
    total_tokens = total_input + total_output
    # Import the same centralized pricing used by the single-agent arm.
    from cost import calculate_cost
    cost = sum(
        calculate_cost(call["input_tokens"], call["output_tokens"], GROQ_MODEL)
        for call in usage_log
    )
    trace_id, trace_file = save_run_trace(
        system="orchestrator",
        question_id=question_id,
        question=question,
        iterations=len(usage_log),
        tool_calls=tool_log,
        llm_calls=usage_log,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total_tokens,
        total_cost=cost,
        elapsed_seconds=elapsed,
        termination_reason=TERMINATION_COMPLETED,
        final_answer=answer,
        model=GROQ_MODEL,
    )
    return {
        "system": "orchestrator",
        "question_id": question_id,
        "question": question,
        "answer": answer,
        "iterations": len(usage_log),
        "tool_calls": tool_log,
        "llm_calls": usage_log,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "total_tokens": total_tokens,
        "cost": cost,
        "elapsed_seconds": elapsed,
        "termination_reason": TERMINATION_COMPLETED,
        "trace_id": trace_id,
        "trace_file": str(trace_file),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the HR Handbook specialist orchestrator.")
    parser.add_argument("--question", required=True)
    args = parser.parse_args()
    outcome = run_orchestrator(args.question)
    print(outcome["answer"])
    print(f"tokens={outcome['total_tokens']} cost=${outcome['cost']:.6f} latency={outcome['elapsed_seconds']:.2f}s")
