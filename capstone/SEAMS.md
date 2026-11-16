# Seam list (honest, unedited by hindsight)

Compiled while building the integration. Dated 2026-10-28 (the day it was written, not backdated).
Status: **fixed** = fixed and checked, **accepted** = known and left, **open** = not fixed yet.

| # | Seam (where two parts disagree) | What happened | Status |
|---|---|---|---|
| 1 | Agent ↔ MCP | Handbook tools ran in-process; only the policy-registry tools went over MCP. So "MCP-discovered at runtime" was not true for the main tools. | fixed: `dispatch_tool` routes handbook tools through the MCP host (`HR_VIA_MCP`) |
| 2 | Trace id ↔ MCP hop | The trace id was minted at the end of the run, so the MCP server could not log it. | fixed: id minted first, sent in `params._meta.trace_id`, written to `mcp_audit.jsonl` |
| 3 | Group filter ↔ chunking | Naive group tags use each chunk's own text. The chunker repeats 150 chars at a boundary, so a rule that starts in a "technical" part can finish in a chunk tagged "non_technical". A technical caller then never sees the recruitment-drive 1000 INR outstation figure (chunk_57). This is the failure the integration creates. | found in a live run (trace tr_9e2f4f04e005, G06/G07); fix built (`tag_index.py --mode overlap`), **fix not yet measured** |
| 4 | Traces ↔ evidence | Traces stored the answer but not the tool results, so nobody could check a claim afterwards. | fixed: `EVIDENCE` list written into the trace |
| 5 | Logging ↔ PII | Nothing redacted what employees paste. | fixed: `src/redact.py` on write, including the MCP trace log |
| 6 | Agent ↔ budgets | When the budget ran out the user got "No final answer". | partly fixed: a fixed fallback pointing to teamhr@softsuave.com. Root cause (large chunks re-sent every iteration) is **open** |
| 7 | Agent ↔ model API | Groq returned 400 `tool_use_failed` when the model invented a tool argument (L01). | partly fixed: caught, logged as `ERROR:BadRequestError`, fallback shown. Retry is **open** |
| 8 | Eval ↔ quota | Groq free tier allows 200,000 tokens per day. One 30-case run uses about 100k. The first baseline hit the cap at case 13, and 18 results were junk (10-minute 429 waits). | accepted: junk rows removed (archive in `output/baseline_invalid_run1/`), harness now stops on long 429 waits |
| 9 | Guard ↔ answer wording | The grounding check flags "9.5" when the handbook says "9.30 hrs" (the model rewrote it). Correct intent, noisy result. | accepted |
| 10 | Group scoping ↔ "both" chunks | A chunk tagged "both" can leak the other team's rule into an answer (G02 mentioned encashment for a non-technical caller). | partly fixed by prompt wording; **open** if it recurs |
| 11 | Registry MCP server ↔ truth | `policy_registry.json` is placeholder data. | accepted: excluded from the capstone |
| 12 | Citations ↔ hosting | Citations are `file://` links to the local PDF, not a hosted URL. | accepted |
| 13 | Two trace folders | Agent traces and Week 11 traces live in different folders. | accepted |
| 14 | `agent.py` | A `"\\n\\n"` literal bug joined role instructions with the text `\n\n`. | fixed |
| 15 | Eval ↔ judge | The old Week 6 suite does not exist for this app. The 30-case suite is new. Judge agreement needs hand labels. | open: needs a human to fill `judge_labels.csv` |

---

## Updates since the first compile (2026-10-30). The table above is left as written.

| # | Seam | What happened | Status |
|---|---|---|---|
| 3 (update) | Group filter ↔ chunking | Overlap tagging alone fixed the technical side only (miss 10/10 → 0/10) but non-technical callers were still handed the technical tail (bleed 8/8 → 8/8). Added the leading-span trim (`lead_group`/`lead_chars` in `tag_index.py`, `tools._trim_foreign_lead`): bleed 8/8 → **0/8**. Residual: technical callers still see the non-technical rule's opening line, 10/10. | fixed for the non-technical side, measured (`measure_group_tagging.py`); residual **accepted** |
| 7 (update) | Agent ↔ model API | Misdiagnosed on 2026-10-28. Real cause: the model was shown `employee_group` and sent `null`; Groq rejected it (4/30 cases). | fixed: `tools.model_schemas()` hides the parameter from the model; N01 and L05 re-ran clean; L01/N02 **not validly re-run** (quota) |
| 8 (update) | Eval ↔ quota | Hit the 200k tokens/day cap again during the re-run. L01 and N02 rows are quota artefacts. | accepted; rows excluded and named in EVAL_REPORT |
| 15 (update) | Eval ↔ judge | `judge_labels.csv` now holds a `claude_draft_label` column (I labelled 28 valid rows) and an empty `human_label`. Agreement vs drafts: 21/28 = 75%. | **open**: a human must confirm the labels |
| 16 | Eval ↔ assertions | `₹1,000` did not match `1000`: G08 and G10 failed on a correct answer. | fixed (`_norm`, selftest) |
| 17 | Revision guard ↔ answer | "Revisions 9 and 10" (plural) skipped the historical-lookup exemption, so the guard replaced a correct answer (R03). | fixed (`revisions?\s*\d+`, selftest) |
| 18 | Grounding guard ↔ model wording | "chunk 56" and "chunks 17 and 19" were read as figures. | fixed (selftest); L05 not re-run after this fix |
| 19 | Evidence ↔ judge | The judge never saw the revision register, so R01-R04 were judged "unsupported: no excerpts". | fixed (`with_register`, `rejudge` command); **not re-measured** (quota) |
| 20 | Citations ↔ answer | Citations list every retrieved chunk, not those the answer used (G07: 5 cited). | accepted; WEAKNESSES #2 |
| 21 | Agent ↔ refusal | N03 refused with zero tool calls. | accepted; TAXONOMY #7 |
