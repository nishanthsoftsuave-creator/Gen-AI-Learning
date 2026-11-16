# Architecture (one page)

```
 employee question  (+ optional --group)
        |
        v
 [1] redact()  ───────────────►  secrets never reach the model or the logs
        |
 [2] resolve_group()  technical | non_technical | unresolved     (BEFORE any retrieval)
        |  mint ONE trace id  (tr_xxxx)
        v
 [3] AGENT LOOP  (Agentic Ai/agent.py)  ══ MODEL CALL: Groq gpt-oss-20b, 1..N times ══
        |   tool calls:  dispatch_tool() overrides employee_group with the resolved group
        |                (the model cannot widen or switch it)
        v
 [4] MCP HOST  (mcp_host.py)  discovers tools via tools/list at runtime
        |   tools/call  params._meta.trace_id = tr_xxxx     ◄── trace id crosses the hop
        v
 [5] MCP SERVER  hr-handbook  (stdio, mcp_handbook_server.py)   ◄── also served to outside clients
        |   writes output/mcp_audit.jsonl {trace_id, tool, group, latency}
        |   search_handbook / get_policy_section / get_handbook_revisions
        v
 [6] RETRIEVAL  hybrid: dense + BM25 → RRF → cross-encoder rerank   (local, free)
        |   Chroma where = {group in [caller_group, "both", "all"]}   ◄── code-enforced filter
        |   chunk metadata: group, page, source_file   (capstone/tag_index.py)
        v
 chunks + page numbers back up the chain  →  EVIDENCE list
        |
        v
 [7] GUARDS (deterministic, no model):  revision guard · number-grounding check
        |
        v
 [8] CITATIONS  "Employee Handbook · Revision 11 (June 2025) · PDF p.22 · chunk_47"  + file link
        |
        v
 answer + trace file  (question, tool calls, evidence, citations, spans, cost; redacted)
```

## Where the model is called, and where the money goes

- **Model calls:** only in [3] (one per agent iteration, typically 2-5) and in the eval judge.
- **Free:** retrieval, reranking, embeddings, MCP, guards (all local CPU).
- **Money:** 100% of cost is agent-loop tokens. Each iteration re-sends the whole conversation, so
  cost grows with the number of tool calls × chunk size. See `COST_AND_10X.md` for measured numbers.

## One trace id, every hop

`capstone.ask` mints the id → `run_agent(trace_id=...)` → the trace file in
`Agentic Ai/output/traces/` → `mcp_host.TRACE_ID` → `params._meta.trace_id` → server audit line
`mcp_audit.jsonl`. `python find_trace.py` / grep the id finds every record.
