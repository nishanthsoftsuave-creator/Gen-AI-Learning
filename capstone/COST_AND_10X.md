# Cost per question and the 10× plan

Measured 2026-10-30 on the 28 valid eval rows (`output/eval_results.jsonl`, `eval_integrated.summarize`).

## Cost per question

| | Value |
|---|---:|
| Mean cost | **$0.000429** |
| Max | $0.00079 |
| Whole 28-question run | $0.0120 |
| Tokens per question, mean / p95 / max | 4,447 / 8,049 / 8,782 |
| Latency p50 / p95 (one question at a time) | 2.8 s / 17.4 s |
| Of which model calls p50 | 2.1 s |
| Of which MCP tool calls, mean | 0.46 s |

Where the money goes: 100% in the agent loop's model calls (Groq gpt-oss-20b). Retrieval, reranking, MCP and guards are local CPU and cost nothing. Each loop iteration re-sends the whole conversation, so cost grows with tool calls × chunk size. Example trace with per-span cost and latency: `Agentic Ai/output/traces/tr_f6f3390bebc5.json` (G07: 2 model calls, 3,662 in / 405 out, $0.000396, 2.06 s; one MCP call, 0.39 s; total 2.49 s; audit line with the same trace id in `Agentic Ai/output/mcp_audit.jsonl`).

Re-index (a new handbook revision): `capstone.py setup` = **28 s, $0**, 100 chunks, local embeddings.

## What breaks first at 10×: the provider rate limit, not the bill

"Today" = this suite's ~30 questions a day. The numbers:

- **Daily token cap: 200,000 tokens/day** (Groq free tier, recorded in SEAMS #8; hit again today). At 4,447 tokens a question that is **about 45 questions a day**. 10× today (≈300 questions, ≈1.3M tokens) is **6.7× over the cap**. Today's work already tripped it once.
- **Per-minute cap: 8,000 tokens/min** ⇒ about 1.8 questions a minute. 10 questions asked in the same minute already need ≈45,000 tokens: 5.6× over.
- Cost is not the problem: 9,000 integrators × 2 questions a day = 18,000 q/day × $0.000429 ≈ **$7.7/day** at the current per-token price. It is the free-tier quota that fails first. (Arithmetic from the measured mean, not a load test.)

What breaks second (estimates, not measured under load): the MCP handbook server is one stdio subprocess handling one request at a time, with a cross-encoder reranker on CPU (0.46 s per call ⇒ about 2 calls/s per worker). 9,000 in-IDE users need a pool of servers or an HTTP transport.

## Plan, ranked by what it buys

1. Move off the free tier to a paid key with a per-minute limit sized for the peak. Removes the first cliff. Cost ≈ $8/day at 18k questions.
2. Cut tokens per question (the only lever on both cost and rate limit): top_k 3 → 2 and trim chunks to the matched span. Each question re-sends ≈3.6k input tokens; halving it roughly doubles questions per minute. Re-run the suite to confirm no case goes red.
3. Cache answers for identical (question, group) pairs. Handbook questions repeat heavily; a hit costs 0 tokens.
4. Replace the single stdio MCP server with a pool or HTTP transport once concurrency exceeds ~2 requests/s.
5. Retry once on a provider 400/429 with backoff instead of showing the fallback (the cheap half of seam 7).
