# Eval report: integrated HR Handbook engine

Written 2026-10-30. Every number below comes from a file in `capstone/output/`; the command that makes it is next to it.

## 1. The number that moved

**Group-aware answers. Before: 3/10. After: 9/10** (the 10 group cases G01-G10, one run each).
Deterministic retrieval check behind it (`python capstone/measure_group_tagging.py`, no LLM, 18 probe queries):

| Index state | Technical caller misses their own rule (n=10) | Non-technical caller is handed the other team's figure (n=8) |
|---|---:|---:|
| naive group tags (before) | 10/10 | 8/8 |
| + overlap inheritance | 0/10 | 8/8 |
| + leading-span trim (after) | **0/10** | **0/8** |

Read the 3/10 → 9/10 honestly: of the 6 cases that flipped, **2 (G08, G10) were a bug in my own assertion** (`₹1,000` did not match `1000`, fixed in `eval_integrated._norm`), not the system. The other 4 are system fixes. Each case was run once; the LLM is not deterministic, so a flip of one case is inside run-to-run noise. The 10/10 → 0/10 and 8/8 → 0/8 retrieval numbers are deterministic and are the stronger evidence.

## 2. Suite results (30 cases, assertions decide, judge is advisory)

| Run | n | Pass | Where |
|---|---:|---:|---|
| Pre-fix, naive tags (only 13 cases got a valid run before the Groq daily cap) | 13 | 4/13 (31%) | `output/before_fix_naive_tags/` |
| After group fix, 30 cases | 30 | 22/30 (73%) | `output/run2_before_schema_fix/` |
| After schema-null, revision-guard and reference-regex fixes (6 cases re-run) | 30 as run / **28 valid** | 25/30 as run, **25/28 (89%) valid** | `eval_summary.md`, `output/eval_results.jsonl` |

**Two rows are excluded from the 28:** L01-hr-contact and N02-gratuity. The Groq free-tier daily token cap was hit during the re-run (N02 waited 446 s on 429s; L01 returned an API status error). Those rows say nothing about the system. Re-run them after the quota resets: `python capstone/capstone.py eval --only L01-hr-contact,N02-gratuity`.

Pass rate by mode, 28 valid rows: group_scope 5/6, group_unresolved 2/2, group_split_rule 2/2, lookup 7/9, multi_step 2/2, revision_history 3/3, not_covered 3/3, pii 1/1.

Remaining failures among the 28: G04 (grounding guard flags a correct "9.5 hours", the handbook says "9.30 hours"), L05 (guard flagged "chunks 17 and 19"; the regex is fixed since, but that case was **not re-run**), L08 (true positive: "about 75 days" is the model's own sum, the handbook says up to 2 months).

Cost and latency, 28 valid rows: mean **$0.000429** per question (max $0.00079), mean 4,447 tokens (p95 8,049), latency p50 2.8 s / p95 17.4 s, model-call p50 2.1 s, MCP tools mean 0.46 s.

## 3. Judge agreement: 75%, below the 85% gate

`python capstone/eval_integrated.py agreement` → **21/28 = 75%**, against labels **I (Claude) drafted** by reading each answer against its retrieved evidence. The `human_label` column in `judge_labels.csv` is empty; **these are not hand labels until you confirm or overwrite them**. When you fill `human_label` the same command uses yours.

The 7 disagreements:
- 4 (R01-R04): the judge never saw the revision register, so it said "unsupported: no excerpts retrieved" about correct answers. **Pipeline bug, fixed** (`with_register`, seam 19). Not yet re-measured because the daily quota ran out. Run `python capstone/eval_integrated.py rejudge` after the quota resets. If those four flip, agreement would be 25/28 = 89%. That is a projection, not a result.
- 2 judge errors on reading (G04 restatement, G07 team label that is in chunk_56).
- 1 judge too lenient (L08 derived "75 days").

Also true: the judge is the same 20B model that wrote the answers. It is advisory and nothing in the pass rate depends on it.

## 4. What this suite does NOT cover

- **Variance:** one run per case. No repeated runs, so no confidence interval; a single-case flip is noise.
- **Realism:** 30 cases written by me from one handbook, not real employee questions or phrasings.
- **One document, one revision (11).** Nothing tests two live revisions at once; the "version" axis here is the employee group.
- **Group is self-declared** (argument or inferred from the question). Nothing authenticates who is asking.
- **Citation precision:** citations list every retrieved chunk, not only the ones the answer used (G07: 5 cited, at most 2 used). Not measured.
- **Faithfulness beyond figures:** deterministic checks cover numbers and emails only. Claims in words (G03's "forfeited") are caught only by the judge, at 75% agreement.
- **PII:** one case, two secret shapes (an API key and a connection string). Other secret shapes are untested.
- **Load:** no concurrency test; latency numbers are one question at a time.
- The technical caller still sees the opening of the non-technical rule (10/10 probes, accepted, see WEAKNESSES.md).

## 5. The hostile questions

**"Does your retriever FILTER on group, or is it words in the text?"** Filter. Chroma `where group in [caller, both, all]`, enforced in `tools.dispatch_tool` (code overwrites whatever the model passes) and, since today, the model is not even shown the parameter. Case G07 plus `measure_group_tagging.py` (0/10, 0/8).

**"Does anything execute a check on emitted content, or is 'looks right' the bar?"** Yes, deterministic: `find_ungrounded` requires every figure and email in an answer to appear in the retrieved text, `cites_revision` requires the revision label, and `secret_in_logs` greps the trace and MCP logs. Cost of that check: 2 of its 4 flags in the 30-case run were false positives (G04, G06), 1 was a true positive (L08).

**"Why is [noisy source] in your corpus, and what does dropping it cost?"** The HR analog does not exist: the corpus is one PDF. Not measured; the other PDFs in `uploads/` are not indexed.

**"v3.1 ships next month. What does re-indexing cost and which case goes red?"** Handbook Revision 12: re-index (`capstone.py setup`) took **28 s and $0** for 100 chunks (local embeddings). Red the next morning: R01 (expects "11" and "June 2025"), R02/R03 if dates move, and every answer case through the `cites_revision` assertion (hard-codes "Revision 11"), plus any case whose chunk boundaries shift. So the suite does watch the thing that moves, but through one hard-coded string; that string should come from `handbook_revisions.json`.

**"Faithfulness is X%. Which part?"** Judge said "supported" on 21/30 as stored (70%), but 4 of the 9 "unsupported" are the register blind spot and 2 are judge errors. By my labels, genuinely unsupported answers are G03, L02, L08 (3/28 = 11%). None is in the group-scoped pay or leave rules; L08 is a derived duration.
