# Week 11 Task Set E — HR Handbook

## Find result

- **Failure:** The answer said the Handbook had 8 revisions and named November 2022 as latest.
- **Trace:** `tr_dc724d3e4324`, 2026-10-16 11:09:55 UTC (16:39:55 IST).
- **Search slice:** Retrieved context IDs. `chunk_97` held the partial revision history ending at Revision 8; it did not establish that 8 was the total. The canonical handbook register lists Revisions 1–11, latest June 2025.
- **Time-to-find:** **Not measurable retrospectively.** No squadmate timer or search-start timestamp was recorded, so I cannot claim mm:ss or under five minutes. The missing evidence is the timed-search start/end field (and the named squadmate); this was a log review after the complaint, not a timed live drill.

## Failure-to-test loop

Added `HR-REV-001` to `week11_eval_cases.jsonl` before applying the fix. The local HR regression replay uses the logged answer as its before fixture. It failed before the fix (0/1) and passed after (1/1). There is no Week 6 answer-quality suite in this checkout; this one-case suite is not represented as a run of that missing suite.

## Fix and ship plan

Prompt version **rag_v1 → rag_v2**: revision questions now include the complete authoritative revision register. A deterministic answer guard replaces a model response if its revision count, latest revision number, or latest date conflicts with that register.

- Canary: route 5% of handbook revision-history questions through rag_v2 for 30 minutes; promote only if all answers match the register and p95 latency rises by less than 10%.
- Rollback: restore rag_v1 and disable the revision guard if any answer disagrees with the register or the canary latency threshold is exceeded.

## Trace limits

The paired application run logged total elapsed time, usage, and cost, but did not log separate retrieval and generation durations. `trace.json` preserves those span latencies as unavailable rather than estimating them. The retrieval context IDs and prompt version are present from the paired request evidence.
