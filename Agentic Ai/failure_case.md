# Injected Worker Failure

Case: Q7 (existing unchanged HR evaluation case).
Worker: policy-content specialist (the narrow worker that searches handbook
policy text). Injection: one synthetic HTTP 500 at its hand-off.

Injected policy-content worker HTTP 500 was returned to the orchestrator.
Observed behavior: The orchestrator degraded to a partial answer; the unchanged judge marked it failed. No automatic retry was added by the worker
adapter; the orchestrator received the error and decided what to do next.

Outcome evaluator: FAIL; details: `{"missing_required": ["suspension", "termination"], "any_group_satisfied": true, "min_matches_satisfied": true}`.
**A2A mapping:** with no usable fallback, this input is sufficient so the task should end `failed`, not `input-required`; asking the user cannot fix a worker outage.
**A2A over plain REST:** A2A standardizes AgentCard/skill discovery and task status such as `working`, `input-required`, and `failed`. A plain REST worker call needs custom conventions for discovery, progress, and recovery.
Run answer:

> I’m sorry, but I couldn’t retrieve the information about disciplinary consequences from the available resources.

Recorded orchestration calls: `[{"iteration": 1, "tool": "delegate_policy_content", "worker": "policy-content", "task": "What are the possible disciplinary consequences for repeatedly or intentionally failing to follow the Employee Handbook?", "error": "injected worker gateway HTTP 500"}]`.
