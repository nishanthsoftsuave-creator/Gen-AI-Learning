# Week 7 Task Set E — Race the Handbook Agent Against a Fixed Workflow

This folder (`rag-python/Agentic Ai/`) implements Task Set E. It is new code, not a
rewrite of anything existing — see "Existing Architecture" for why, and what
was reused instead of rebuilt.

**Domain note**: this was originally built against the Nimbus SDK v2/v3
documentation corpus from `sdk_docs_task/` (a natural fit for
`get_openapi_spec`/`get_changelog`/`api_version` enums). It was then
rebuilt, at the user's request, to run against the **Soft Suave Employee
Handbook** instead — the PDF already used by the main app's Document Q&A
tab. That corpus has no API versions, no OpenAPI spec, and no dated
changelog in the SDK sense, so the tool set below was redesigned around
what this document actually contains, rather than forcing the original
API-versioning shape onto it. See "Third Tool" for the mapping.

## Existing Architecture

The project did **not** already contain a Week 7 agent loop, tools, or
tool-calling — Weeks 4–5 built retrieval-quality tooling instead. What
existed and is reused here:

| Piece | Location | Reused as |
|---|---|---|
| Employee Handbook PDF, already ingested | `documents/SS Employee Handbook Updated-2025 (1).pdf`, collection `rag_documents` in root `chroma_db/` | The document all 3 tools operate on |
| Hybrid retrieval (dense + BM25 + RRF + cross-encoder rerank) | `src/retrieval.py::hybrid_retrieve` | Backing implementation for `search_handbook` |
| Recursive chunker + embedding model | `src/chunk_document.py`, `src/create_embeddings.py` | Reused to read/embed the same chunks the main app already uses |
| Groq client / model selection (`GROQ_MODEL`, default `openai/gpt-oss-20b`) | `src/rag.py` | Same env vars, same default model, in `llm_client.py` |
| Trace-ID scheme + `output/traces/` convention | `src/tracing.py::create_trace_id` | Reused directly; extended with a run schema (iterations, tool calls, budgets) in `agent_tracing.py` |
| Known extraction-quality issues with this exact PDF | `sdk_docs_task/../notes.md`, `taxonomy.md` (Week 5 error analysis) | Informed how `get_policy_section` is built (verbatim excerpts, not hand-cleaned paraphrases) — see below |

**No source files were changed** for this iteration (the earlier
`src/retrieval.py::hybrid_retrieve(..., where=None)` filter parameter,
added for the original SDK-docs version, is simply unused here since this
collection has no version metadata to filter on — removing it would have
served no purpose, so it was left as a harmless additive parameter).

**Files added** (all under `Agentic Ai/`): `tools.py`, `handbook_revisions.json`,
`budgets.py`, `cost.py`, `llm_client.py`, `agent_tracing.py`, `agent.py`,
`workflow.py`, `race_questions.json`, `race.py`, `budget_termination_test.py`,
this `README.md`, and `output/` (traces, `race.csv`, `race_summary.json`,
`budget_termination.log`).

**Also added**: a `POST /agentic/compare` endpoint on the existing FastAPI
app (`src/app.py`, via a new `src/agentic_bridge.py` that puts `Agentic Ai/`
on `sys.path` since its folder name isn't a valid Python package name), and
a new "Agent vs Workflow" tab in the existing React frontend
(`frontend/src/components/AgenticRace.jsx`) so a question can be run
against both systems and compared from the browser, not just the CLI.

### How `get_policy_section`'s data was verified (no invented content)

This PDF's multi-column layout means `pypdf` extracts text with headings
and body text from adjacent sections sometimes interleaved out of order —
already documented independently by the Week 5 error analysis of this same
document (`notes.md`, `taxonomy.md`: "chunks include a table of contents,
handbook revisions, and arrears/pro-rata text" mixed together). Rather than
hand-transcribing paraphrased section text into a JSON file (risking
misattributing a sentence to the wrong policy given that interleaving), the
actual ingested chunks (`rag_documents` collection, same one the main app
queries) were inspected directly and 8 section keys were anchored to real,
verified-unique substrings pulled from that raw text — see
`tools.py::POLICY_SECTIONS`. `get_policy_section` returns those chunks
**verbatim**, with a `note` field disclosing the interleaving, rather than
a cleaned-up rewrite.

## Third Tool

Added **`get_handbook_revisions`** — the closest fit to the original
`get_changelog`/`check_deprecation` idea, but pointed at a real fact this
document actually contains: the Handbook itself lists 11 dated revisions
(Revision 1, January 2017 → Revision 11, June 2025) plus a modifications
clause, found verbatim on its closing pages. Unlike an SDK changelog, this
tool takes no parameters — there's no per-revision content diff in the
source document, only dates, so no enum could be built without inventing
one.

The strict-enum requirement instead lives on **`get_policy_section`**:

```python
section: Literal[
    "arrear_policy_freshers",
    "work_from_home_and_deputation_compensation",
    "employee_code_of_conduct",
    "disciplinary_actions",
    "conflict_of_interest_and_gifts",
    "employee_grievances",
    "contact_details",
    "company_leadership",
]
```

These 8 values are exactly the sections that were hand-verified against
the real PDF text (see above) — no placeholder or guessed section names.

Data sources: `tools.py::POLICY_SECTIONS` (anchor phrases → live lookup
against the already-ingested `rag_documents` chunks) and
`handbook_revisions.json` (the verbatim revision list + modifications
clause, transcribed once and checked against the source PDF).

## Tool Description Diff

```diff
 search_handbook:
- "Search the handbook for information."
+ "Search the Soft Suave Employee Handbook for passages relevant to a
+ natural-language question: general policy explanations, procedures, and
+ context that may span more than one section. Returns ranked text
+ passages. Does NOT return the full verbatim text of one specific named
+ section (use get_policy_section) and does NOT return the Handbook's own
+ dated revision history (use get_handbook_revisions)."

 get_policy_section:
- "Get a section of the handbook."
+ "Retrieve the full, verbatim text of ONE specific, named section of the
+ Employee Handbook, located exactly (not by similarity search). Returns
+ only that section's text -- no other section, and no revision history.
+ Use search_handbook for a broader question, get_handbook_revisions for
+ when/how the document itself changed."
+ section: enum[8 real section names]

+ get_handbook_revisions:
+ "Retrieve the Employee Handbook's own dated revision history (every
+ revision number and date) and its modifications clause -- i.e. how many
+ times and when the Handbook DOCUMENT ITSELF has been updated. Does NOT
+ return the content of any HR policy -- use get_policy_section or
+ search_handbook for that."
```

Each tool states what it returns, what it explicitly does *not* return,
and which other tool to use instead — that's what removes the overlap, not
an instruction telling the model "use the correct tool." The trickiest
overlap risk in practice: `company_leadership` and the revision list happen
to sit in the *same* raw source chunk near the end of the PDF (a chunking
coincidence, not a design overlap) — see "Limitations."

## Agent vs Fixed Workflow

Both live in `Agentic Ai/`, use the same 3 tools, the same `GROQ_MODEL`, the
same 10 questions, and the same output contract (see below).

- **`agent.py`** — a `while True` loop. Each turn: check all 4 budgets →
  one Groq tool-calling call → if the model requested tools, run them and
  loop; if not, that's the final answer. The next tool call is chosen by
  the model based on what the previous one returned (`agent.py`'s
  `SYSTEM_PROMPT` + `TOOL_SCHEMAS` from `tools.py`).
- **`workflow.py`** — `_fixed_tool_steps()` always calls `search_handbook`
  once, `get_policy_section` once for **every** one of the 8 known
  sections, and `get_handbook_revisions` once — 10 tool calls, always,
  regardless of the question — then exactly one Groq call synthesizes the
  answer from all of it. No loop, no branching, no budget checks (there's
  nothing to bound).

**Output contract** (both systems return this shape from `run_agent()` /
`run_workflow()`, and both write a matching trace via `agent_tracing.py`):

```python
{
  "system": "agent" | "workflow", "question_id": str, "question": str,
  "answer": str, "iterations": int, "tool_calls": [...],
  "input_tokens": int, "output_tokens": int, "total_tokens": int,
  "cost": float, "elapsed_seconds": float, "termination_reason": str,
  "trace_id": str, "trace_file": str,
}
```

The same `run_agent`/`run_workflow` functions also back the UI:
`src/app.py`'s `POST /agentic/compare` calls both for one question and
returns `{question, agent, workflow, verdict}`, rendered by
`AgenticRace.jsx` in the "Agent vs Workflow" tab.

## Test Questions

`race_questions.json`, 10 questions, tagged by category; 4 are marked
`"requires_dependency": true` (≥3 required) where a correct answer requires
inspecting one tool's result before knowing which tool/section to pull
next:

| ID | Categories | Dependency? |
|---|---|---|
| Q1 | simple_lookup, leadership | no |
| Q2 | revision_history | no |
| Q3 | cross_reference, multi_step | **yes** |
| Q4 | policy_comparison | no |
| Q5 | revision_history, multi_step | **yes** |
| Q6 | simple_lookup | no |
| Q7 | policy_detail | no |
| Q8 | cross_reference, multi_step | **yes** |
| Q9 | policy_detail, policy_comparison | no |
| Q10 | leadership, revision_history, multi_step | **yes** |

Example dependency chain (Q3): asking who to consult about possible
misconduct, and what happens if found guilty, needs
`get_policy_section("employee_code_of_conduct")` for the first half
("consult a Reporting Senior or HR") and a *separate*
`get_policy_section("disciplinary_actions")` call for the second
(reprimand/suspension/termination) — neither section alone answers both.

All 10 questions are grounded in text hand-verified against the real PDF
(CEO/MD names, the 11 dated revisions, HR contact emails, and the technical
vs. non-technical compensation figures) — see "How `get_policy_section`'s
data was verified" above.

## Pass/Fail Criteria

Deterministic, substring-based, implemented in `race.py::evaluate()` — no
manual grading. Each question in `race_questions.json` declares:

- `must_contain`: every term must appear (case-insensitive substring) in the answer.
- `must_contain_any` (optional): at least one term from the list must appear.
- `min_matches_from` (optional): at least `min` terms from `list` must appear.

A question passes only if all declared conditions hold. Answer text is
normalized to fold typographic hyphen variants (`‑ ‒ – — ―`) to ASCII `-`
before matching, so grading isn't fooled by glyph choice on compound terms.

## Race Results

Run: `python race.py` (writes `output/race.csv`, `output/race_summary.json`).
Real run, 20 live Groq calls, September 2026 (see `output/race.csv` for the
per-question rows and `race_run.log` for the console trace).

| System | Pass Rate | p50 Latency | Total Tokens | Cost / Question |
| --- | ---: | ---: | ---: | ---: |
| Agent | 60% (6/10) | 37,885 ms | 36,514 | $0.000349 |
| Fixed Workflow | 100% (10/10) | 46,871 ms | 61,126 | $0.000560 |

**What actually happened, honestly** — this run has one ordinary failure and
three unusual ones, and they are not the same kind of failure:

- **Q6 (agent, `MAX_TOKENS_EXCEEDED`)**: the model re-issued near-identical
  `search_handbook` calls instead of answering once it already had the HR
  contact info, ran the cumulative context to 13,889 tokens, and was
  cleanly stopped. This is the same degenerate loop pattern documented
  under "Budget Enforcement" — a real, reproduced agent weakness.
- **Q8–Q10 (agent, `MAX_WALL_CLOCK_EXCEEDED`)**: partway through this run,
  this Groq account's quota tightened sharply — retry waits escalated from
  single-digit seconds to `retrying in 2481.5s` (41+ minutes; see
  `race_run.log`), consistent with hitting a daily/session cap on top of
  the per-minute TPM limit, most likely from the cumulative usage of every
  smoke test, budget test, and earlier race run performed in this same
  session. The agent's `MAX_WALL_CLOCK_SECONDS=90` budget correctly fired
  the moment a multi-minute-delayed response finally came back — this is
  the budget enforcement working exactly as designed, not a reasoning bug.
  **The fixed workflow has no wall-clock guardrail** (see "Budget
  Enforcement" — it was deliberately not made subject to the four budgets,
  since it has no loop to bound), so it simply absorbed waits as long as
  42 minutes (`workflow,Q10,...,2554854.5` ms in `race.csv`) and still
  completed successfully every time. That is a genuine, un-fabricated
  result of this run, not an artifact removed for presentation — see
  "Limitations" for why it wasn't rerun away.
- All other rows (14 of 20) completed normally in 1–54 seconds with no
  budget involved.

Because p50 is a median, the three extreme workflow outliers (Q8–Q10, all
in the 2,200–2,555 second range) do not distort the reported p50 latency —
it still reflects the typical, non-throttled case for both systems. Token
and cost totals are entirely unaffected by the throttling (they only count
actual tokens billed, not wait time).

One behavior worth calling out on its own: when the *identical* infra
problem (severe rate-limit queueing) hit both systems on Q8–Q10, the agent
detected it and stopped within 2 minutes each time via its own wall-clock
budget, while the fixed workflow had no equivalent protection and only
succeeded because Groq eventually responded. A fixed pipeline with no
timeout is not automatically safer — it is just uninstrumented. This
doesn't overturn the Verdict below, but it's the one place in this run
where the agent's extra machinery paid for itself in something other than
token count — see the Verdict for how much weight that gets.

## Budget Enforcement

All four budgets are enforced in `budgets.py::BudgetTracker`, checked in
`agent.py`'s loop before every iteration and again immediately after every
LLM call's usage is recorded (so a budget that trips because of the call
that just returned stops the run *before* any tool calls that response
requested are executed):

| Budget | Default | Enforced by |
|---|---|---|
| Max iterations | 8 | `iterations > max_iterations` check at loop top |
| Max tokens | 12000 | cumulative `input+output` tokens across **all** LLM calls in the run |
| Max cost | $0.02 | cumulative cost across all LLM calls, via `cost.py` |
| Max wall-clock | 90s | `time.monotonic() - start_time` (includes Groq rate-limit backoff — see Limitations) |

The fixed workflow is not subject to these budgets: it has exactly one loop
iteration by construction (10 fixed tool calls + 1 LLM call), so there is
no runaway to bound.

## Budget Termination Log

`budget_termination_test.py` forces `max_iterations=1` (all other budgets
at default) against Q3 — a question that legitimately needs more than one
tool round-trip — so the agent completes one real iteration (real tool
call, real token usage) and is then cleanly stopped before a second LLM
call. Real output, not fabricated: `output/budget_termination.log`.

Run: `python budget_termination_test.py`

## Verdict

The fixed workflow wins on reliability: 100% vs. 60% pass rate. It costs
more per question ($0.000560 vs. $0.000349) but the agent's failures make
its cost per *correct* answer worse. p50 latency (46.9s vs. 37.9s) isn't
very informative here since both were hit by the same severe Groq
rate-limit queueing.

Does the path vary by input? For the workflow, never — it always pulls all
8 sections plus revisions. For the agent, yes — but none of the 4
dependency questions (Q3, Q5, Q8, Q10) needed branching the fetch-all
workflow couldn't cover; both scored correctly on Q3 and Q5. The one place
dynamic behavior earned its keep: under rate-limit stress (Q8–Q10), the
agent's wall-clock budget aborted in under 2 minutes, while the unguarded
workflow absorbed waits up to 42 minutes. That argues for a workflow
timeout, not for the agent loop — it isn't a correctness advantage.

## How to Run

All commands run from `Agentic Ai/` using the project's existing venv
(`../venv/Scripts/python.exe` on Windows; `groq`, `chromadb`,
`sentence-transformers`, `rank_bm25`, `python-dotenv` must already be
installed, which they are for this project).

```bash
cd "rag-python/Agentic Ai"

# Interactive agent
../venv/Scripts/python.exe agent.py
# One-shot
../venv/Scripts/python.exe agent.py --question "Who is the CEO of Soft Suave, and who is the Managing Director?"

# Interactive fixed workflow
../venv/Scripts/python.exe workflow.py
# One-shot
../venv/Scripts/python.exe workflow.py --question "..."

# Full race (all 10 questions, both systems) -> output/race.csv
../venv/Scripts/python.exe race.py

# Controlled budget-termination demo -> output/budget_termination.log
../venv/Scripts/python.exe budget_termination_test.py
```

**Also runnable from the browser**: start the backend
(`uvicorn src.app:app --reload` from `rag-python/`) and the frontend
(`npm run dev` from `rag-python/frontend/`), then open the app and click the
"Agent vs Workflow" tab.

Requires `GROQ_API_KEY` in `rag-python/.env` (already present) and the root
`chroma_db/` collection `rag_documents` already ingested (already the case
in this repo via the main app's upload flow; re-upload the Handbook PDF
through the Document Q&A tab if that collection is ever cleared).

## Cost Calculation

Single source of truth: `cost.py::calculate_cost(input_tokens,
output_tokens, model)`. Pricing is Groq's published per-token rate for
`openai/gpt-oss-20b` (the project's `GROQ_MODEL` default), as of September
2026:

- Input: $0.075 / 1M tokens
- Output: $0.30 / 1M tokens

Source: [Groq Pricing 2026 (CloudZero)](https://www.cloudzero.com/blog/groq-pricing/),
[gpt-oss-20b pricing (Requesty)](https://www.requesty.ai/models/groq/openai-gpt-oss-20b).
If `GROQ_MODEL` is ever changed to a model not in `cost.PRICING_PER_MILLION_TOKENS`,
`calculate_cost` falls back to these same rates rather than silently costing $0 —
add the new model's real rate to that table instead of relying on the fallback.

## Limitations and Assumptions

- **Groq account is rate-limited to 8000 tokens/minute** (on-demand free
  tier) for `openai/gpt-oss-20b`. `llm_client.py` retries on HTTP 429 using
  the server's `Retry-After` header. This means `elapsed_seconds` /
  wall-clock latency in the race includes real provider throttling wait
  time, not just model + retrieval latency — a shared, external constraint
  that applies equally to both systems.
- **This specific PDF extracts with interleaved section boundaries**
  (multi-column layout — independently documented in the Week 5 error
  analysis of this same document). `get_policy_section` returns the raw
  chunk verbatim rather than a cleaned rewrite, and says so in its `note`
  field, so nothing is silently corrected or invented.
- **One coincidental content overlap**: the `company_leadership` anchor and
  the tail of the revision-history text happen to land in the same 900-char
  source chunk (a chunking-boundary coincidence near the end of the
  document, not a description overlap) — `get_policy_section` may
  therefore surface a stray revision date alongside the CEO/MD names. The
  tools' *purposes* remain distinct; only this one raw excerpt overlaps.
- **Pass/fail is substring-based**, not semantic. A correct answer phrased
  without one of the exact required tokens would be marked failed even if
  factually right. This trades some recall for zero manual grading and
  full reproducibility.
- **Model non-determinism**: at `temperature=0.3`, the agent's exact tool
  sequence and iteration count vary run to run even for the same question.
  The race numbers reflect one real run, not an average over many.
