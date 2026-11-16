"""Compatibility name for the handbook multi-agent orchestrator."""

from orchestrator import run_orchestrator


def run_multi_agent(question, question_id="adhoc"):
    result = run_orchestrator(question, question_id=question_id)
    result["system"] = "multi_agent"
    return result
