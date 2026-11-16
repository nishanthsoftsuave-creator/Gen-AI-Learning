# Week 11 Task Set E, HR Handbook: stale leave-policy answer

## Find result

- **Planted trace:** `tr_5e0d17a94c3b`, 2026-10-21 09:14:22 UTC, user `u_71de`, `rag_v1`. It tells technical staff they can carry forward 12 leaves. The handbook (section 9, `chunk_47`) says technical staff's unused leave is encashed, and only non-technical staff carry forward (max nine).
- **Slice that found it:** time (97 traces down to 2), then input type `category=leave` (down to 1). Text search on the answer also works (`--text carry`).
- **Time-to-find: NOT MEASURED as a valid drill.** I planted the answer myself, so the search was not blind, and no squadmate held a stopwatch. The only number I have is the machine run time of `find_trace.py` (0.26 s), which says nothing about a human search. **A real mm:ss needs a squadmate to plant a different answer and time it.** Name that squadmate here when it is done: `____ : ____ (timed by ____)`.
- **Log field whose absence would have cost the time:** `category` and `user_ref`. The 81 traces written before this session have neither (`cat=None user=None`), so for them only time and text search work. Per-span latency and cost were also missing until now.

## Failure-to-test loop

Cases are in `week11_eval_cases.jsonl`; output is in `suite_week11_v3.txt`.

| Run | Result | Cases |
|---|---|---|
| RED, before the fix | **2/4** | HR-REV-001 fail, HR-LEAVE-001 fail (replays the planted answer); legacy and non-technical cases pass |
| GREEN, after the fix | **4/4** | HR-LEAVE-* run live on `rag_v3` |

Things you must know about this result:

- **The 4-case suite is not the Week 6 suite.** That suite is not in this checkout.
- **RED is a replay of the planted answer.** The bad answer was never produced by the current pipeline.
- **The old prompt already passed.** `rag_v2` answered the planted question correctly 3 out of 3 times live (encashment, no "12"). So the prompt bump is hardening, not a proven cause-and-effect fix. I can't show that a prompt change made the failure go away, only that the new case catches this answer.
- **Regression found along the way.** The earlier revision guard broke the legacy case `HR-REV-002-legacy`, an old pass-through case (suite `1/2`). I fixed the guard and the suite went to `2/2`.
- **I corrected `HR-LEAVE-002-nontech` after one bad run.** It first forbade "encash", but the correct answer legitimately mentions technical encashment. It now forbids the wrong figures (12) instead.

## Fix and ship plan

Prompt **rag_v2 to rag_v3** (`src/rag.py`, version constant in `src/tracing.py`, so traces now show the real version): state a policy figure only if it appears in the context, and only for the employee group the context names.

- Canary: serve `rag_v3` to 5% of leave/payroll/benefits questions for 30 minutes (filter with `find_trace.py --category leave --prompt-version rag_v3`); promote only if every sampled figure matches the handbook and p95 latency rises less than 10%.
- Rollback: set `PROMPT_VERSION` back to `rag_v2` and remove the added paragraph from the prompt if any sampled answer states a figure not in its retrieved chunks, or the p95 latency threshold is exceeded.

## Diagnosis note

Retrieval served `chunk_47, chunk_46, chunk_45`, all from `SS Employee Handbook Updated-2025 (1).pdf` and including the correct rule. So a stale answer like this one comes from the model, not from retrieval of an archived page. Only one handbook revision is indexed, so `source_revision` is not logged; `source_file` is.

## Blind timed drill (to fill in with a squadmate)

1. Squadmate runs `python plant_stale_answer.py --manifest <path you cannot see>`. It plants one stale answer at a random user and time (2-6 days ago) and prints nothing about it.
2. Squadmate says only: "someone said it quoted an old HR policy last week", and starts the stopwatch.
3. You find it with `python find_trace.py` (`--since/--until`, `--category`, `--text`). Stop the clock when you say the trace id.
4. Squadmate checks the id against the manifest.

| Run | Slice that found it | Time (mm:ss) | Timed by | Under 5:00? |
|---|---|---|---|---|
| 1 (first plant) | | | | |
| 2 (bonus: second plant, same tool) | | | | |

Field that closed the gap between run 1 and run 2 (bonus): `________`

## Not done

- A valid timed drill (see above) and the bonus (second plant, beat your own time).
- The planted trace's spans and context ids are copied from real trace `tr_91795918c2d0`, not from a fresh request.
