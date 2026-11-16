# Fresh-eyes note

**Status: NOT DONE.** This needs a real reviewer from another squad running the system with their own client. I have not filled in any field below and the demo should not claim it was done until a person does.

| Field | Fill in |
|---|---|
| Reviewer (name, squad) | |
| Date | |
| Their MCP client | |
| Where they stumbled | |
| What you changed because of it | |

## What to hand the reviewer
1. Repo root `rag-python/`, `README` in `capstone/`.
2. To call the MCP server from their own client, add to its MCP config:
   ```json
   {"mcpServers": {"hr-handbook": {"command": "python", "args": ["capstone/capstone.py", "serve-mcp"]}}}
   ```
   Tools: `search_handbook(query, top_k, employee_group)`, `get_policy_section(section, employee_group)`, `get_handbook_revisions()`. First `tools/list` takes about 25 s (embedding model loads).
3. Have them include a `_meta.trace_id` in `tools/call`, then check `Agentic Ai/output/mcp_audit.jsonl` for it.

## What I did instead (not a substitute)
`python capstone/external_mcp_client.py` is a raw JSON-RPC stdio client that shares no code with `mcp_host.py`. It passes 6/6 checks (tools discovered, technical caller gets the outstation ₹1000, non-technical caller is not given the other team's figures, bad section returns a readable error, trace id reaches the audit log, audit log holds no query text). It was written by the same person as the server, so it proves the wire works, not that a stranger can use it.
