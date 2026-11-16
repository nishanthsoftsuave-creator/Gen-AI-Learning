# HR Handbook Answer Engine (Week 12 capstone, HR variant)

Answers Soft Suave Employee Handbook questions for the **caller's actual team** (Technical or
Non-Technical), cites the **handbook revision and PDF page**, says plainly when the handbook does not
cover a topic, and logs one trace id across the agent and MCP hops with secrets redacted.

In the developer-docs brief the "version" is the SDK version. Here it is the **employee group**: the
handbook has different rules per group (leave encashment vs carry-forward, working hours, pay on
non-working days). A wrong-group answer is the analogue of the wrong-version snippet. The citation
version is the handbook revision (latest: Revision 11, June 2025).

## Run it (from the repo root `rag-python/`)

```powershell
python -m venv venv; .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
# put GROQ_API_KEY=... in .env (the model is openai/gpt-oss-20b on Groq, free tier, 8,000 tokens/min)

python capstone/capstone.py setup                       # ingest the handbook PDF + tag chunks by group
python capstone/capstone.py ask "Can I carry forward unused leave?" --group technical
python capstone/capstone.py eval                        # the full integrated suite (30 cases, ~30 min)
python capstone/capstone.py selftest                    # offline checks, no API calls
python capstone/capstone.py serve-mcp                   # expose the handbook tools to any MCP client
python capstone/measure_group_tagging.py                # offline before/after for the group fix (no API)
python capstone/trajectory_integrated.py               # trajectory eval from the last eval run's traces (no API)
python capstone/external_mcp_client.py                 # independent MCP client, 6 checks (no API)
python capstone/eval_integrated.py agreement           # judge vs labels
python capstone/eval_integrated.py rejudge             # re-score stored answers with the current judge (API)
```

`ask` prints the answer, citations (revision + page + link), group and how it was resolved, trace id,
cost, and latency split into model / tools / 429-wait time.

## What is behind the one entry point

| Requirement | Where |
|---|---|
| RAG with version-named citations | `src/retrieval.py` hybrid retrieval; citations built in `capstone.py` |
| Agent loop, 3+ tools, MCP-discovered at runtime | `Agentic Ai/agent.py`; tools come from `tools/list` (`Agentic Ai/mcp_host.py`) |
| MCP server of our own, called by a client that is not ours | `Agentic Ai/mcp_handbook_server.py` (`serve-mcp`) |
| Group resolved before retrieval, enforced by code | `capstone.resolve_group`, `tools.CALLER_GROUP`, Chroma `where` filter |
| Eval suite, assertions before judge | `eval_cases.jsonl`, `eval_integrated.py` |
| Trajectory eval | `Agentic Ai/trajectory_eval.py` |
| One trace id across agent + MCP hop, PII redacted on write | `capstone.ask`, `mcp_host.TRACE_ID`, `src/redact.py`, `Agentic Ai/output/mcp_audit.jsonl` |

## Calling the MCP server from another client

Add to the client's MCP config (for example Claude Code `.mcp.json`):

```json
{"mcpServers": {"hr-handbook": {"command": "python", "args": ["capstone/capstone.py", "serve-mcp"]}}}
```

Tools: `search_handbook(query, top_k, employee_group)`, `get_policy_section(section, employee_group)`,
`get_handbook_revisions()`. A stranger client passes `employee_group` itself; inside our agent the code
overrides whatever the model passes.

## Documents

`ARCHITECTURE.md` · `SEAMS.md` · `TAXONOMY.md` · `EVAL_REPORT.md` (with stated non-coverage) ·
`TRAJECTORY.md` · `COST_AND_10X.md` · `WEAKNESSES.md` · `DEMO_SCRIPT.md` · `FRESH_EYES.md` (template: needs a real reviewer)

Groq's free tier allows 200,000 tokens/day; one full `eval` uses about 125k. If it stops with `STOP after ...`, re-run the rest with `eval --only <ids>` after the quota resets.
