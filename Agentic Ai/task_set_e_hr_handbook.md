# Week 11 Practical — Task Set E (HR Handbook edition)

## Find the answer that quoted a superseded policy

| | |
|---|---|
| Domain | HR handbook documentation (policies, leave, benefits, payroll, conduct) |
| Week | 11 — Production: Observability, Cost & the Failure→Test Loop |
| Module | M6 — Production & Capstone |
| Marks | 100 |

This extends the app you built in Week 11. It is not a build from scratch and it tests only this week's concepts. Bring your numbers written down.

## 1. Problem statement

The complaint: *"An employee said the assistant quoted a leave/policy rule that HR changed, some time last week."*

You get no trace id, no employee, no handbook revision, and no policy name. That is all you will ever get. Find the answer in your Week-11 logs on the clock, then close the loop so this failure can never ship again.

"Superseded" means the answer states a rule from an older handbook revision (or the model's memory) as if it were current. The stale rule is in the **generated answer**, not in the question.

## 2. Requirements

1. **Plant.** A squadmate plants one bad, stale-policy answer in your logs. They describe it only as vaguely as above.
2. **Find.** Locate it from logs alone. Report time-to-find as `mm:ss`, **timed by the named squadmate**, and name the slice that found it: time / user (role or department) / prompt version / input type (policy category) / cost outlier. Under 5:00, or your write-up must name the exact log field whose absence cost you the time.
3. **Trace.** Paste the found trace: per-span latency, tokens and cost, plus prompt version and retrieved context ids (chunk ids **and** the handbook revision each chunk came from).
4. **Eval case.** Turn the failure into an eval case and add it to the existing suite. Run the whole suite and show it **RED before the fix and GREEN after**, with pass counts both times (e.g. `9/10 -> 11/11`).
5. **Fix** at the prompt or retrieval layer (e.g. prefer the current revision, filter or down-rank archived revisions, require a revision citation). Record the prompt version bump. Write a two-line canary and rollback plan.
6. **Cost.** Report cost per query for that request by stage (retrieval / generation / tools). Then answer in one line: at 10x today's query volume, what breaks first (cost, latency or rate limit), with the number that proves it.

## 3. Expected output

- `drill.md` — time-to-find in `mm:ss`, slice used, timed by a named squadmate
- `trace.json` — per-span latency / tokens / cost, prompt version, context ids + revision per chunk
- the new eval case, added to the existing suite (`week11_eval_cases.jsonl`)
- suite output pasted twice: RED then GREEN, with pass counts
- `cost_by_stage.md`
- `tenx.md` — one line + number

## 4. Evaluation rubric

| Criterion | Points |
|---|---|
| Loop closed: eval case seen RED before the fix and GREEN after, suite pass counts both times | 30 |
| Time-to-find in `mm:ss` with the slice named, or the missing log field named honestly | 25 |
| Trace pasted with per-span latency, tokens, cost, prompt version and retrieved context ids | 20 |
| Cost per query by stage and the 10x claim backed by a number | 15 |
| Prompt version bump recorded with a two-line canary and rollback plan | 10 |
| **Total** | **100** |

Zero points for polish, UI, or "it works". Failure-finding and a number that moved are what score.

## 5. Eval case shape (example)

```json
{"id":"HR-LEAVE-001","question":"How many days of carry-forward leave can I keep?","failure_trace_id":"tr_xxxxxxxxxxxx","must_contain":["<current rule>","<current revision>"],"must_not_contain":["<superseded rule>"],"source":"<canonical register / current handbook file>"}
```

Also keep (or add) a **legacy-support case** that must stay green after your fix, for example: *"What was the leave policy in Revision 6?"* must still return the old rule, labelled as historical. A fix that hides old revisions entirely breaks this.

## 6. Bonus challenge

Add the missing log field or index that would have made the find instant. Have your squadmate plant a second stale answer and beat your own time. Report both times and the one field that closed the gap.

## 7. Submission checklist

- [ ] `drill.md` — `mm:ss`, slice, **timed by a named squadmate** (not a retrospective log review)
- [ ] `trace.json` — per-span latency/tokens/cost, prompt version, context ids + revision per chunk
- [ ] Eval case file, added to the existing suite
- [ ] Suite output pasted twice (RED before, GREEN after), pass counts on both
- [ ] `cost_by_stage.md` — retrieval / generation / tools
- [ ] `tenx.md` — what breaks first at 10x, with the number

## 8. Log fields you need *before* the drill

If these are missing, add them first. A missing field is the usual reason the find takes more than five minutes.

| Field | Why |
|---|---|
| `timestamp` (UTC) | the "last week" time slice |
| `user_ref` + `role`/`department` (hashed id, never raw name or salary data) | the user slice |
| `prompt_version` | the prompt-version slice |
| `category` (leave / payroll / benefits / conduct / revision-history) | the input-type slice |
| `question` **and** `answer` both searchable | the complaint describes the output |
| `retrieval.chunks[]` with `chunk_id` **and** `source_revision` | tells you whether retrieval served an archived revision or the model answered from memory |
| per-span `latency_ms` (retrieval, generation, tools) | span latency in the trace |
| per-span `tokens_in` / `tokens_out` / `cost_usd` | cost by stage and cost-outlier slice |

HR logs contain personal data. Index the hashed user ref, keep raw question text access-restricted, and say in `drill.md` who can read the logs.

## 9. Common mistakes

- Optimising before attributing cost by stage, so you cannot say which change moved the number.
- Fixing the prompt first and adding the eval case afterwards. A test that has only ever been green is a test you have not tested.
- Searching only the question when the complaint describes the answer. Index both.
- Seeing the new case green and not re-running the rest of the suite. Your "use the current revision" fix can quietly break the legacy-support case.
- Not logging `source_revision` per retrieved chunk, so you cannot tell archived-page retrieval from model-memory error. That is a two-day mystery instead of a one-hop diagnosis.
- Claiming a time-to-find from a retrospective log review. No squadmate timer means no `mm:ss`; say so honestly and name the missing field.
- Routing this query type to a cheaper model as your fix without re-running the suite.
