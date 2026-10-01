Maintainer: HR Platform Team -- placeholder ownership; actual maintainer and code provenance must be verified before deployment (no real person is claimed).
Reach: Read-only access to the local HR policy registry file (policy_registry.json: policy ids, versions, dates, statuses); no employee PII, no database, no network egress, no other systems.
Logging: Tool name, policy id, arguments, timestamps, and error text are appended to Agentic Ai/output/mcp_trace.jsonl (server stderr to mcp_hr-policy-registry_stderr.log); secrets and tokens must never be logged.
Stolen token: Could allow an attacker to invoke the four registry tools and read policy metadata within the token's granted scope -- so any token introduced later must be least-privilege, short-lived, and read-only for policy lookups.
Decision: Ship only after source review, least-privilege token scope, logging review, and authentication/authorization testing -- all four conditions must be satisfied first.
