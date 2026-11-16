# 10-minute demo script (HR Handbook edition)

Mapping from the SDK brief: SDK version → **employee group** (Technical / Non-Technical); "that method no longer exists in 3.0" → **"That is not covered in the Employee Handbook."**; deprecation surfaced unasked → the **other team's differing rule** surfaced when it appears in the evidence.

Before you start (do these once, the demo should not depend on the API being up):
```powershell
.\venv\Scripts\Activate.ps1
python capstone/capstone.py selftest          # offline, 10 s
python capstone/measure_group_tagging.py       # offline, ~1 min: the before/after table
python capstone/external_mcp_client.py         # offline: independent MCP client, 6 checks
```
If Groq's daily quota is spent, Parts 1 and 3's live questions will fail. Say so, show a stored trace (`Agentic Ai/output/traces/tr_f6f3390bebc5.json`) and keep going; Parts 2-4 are mostly offline.

## Part 1: a real run (3 min)
1. `python capstone/capstone.py ask "I'm on the technical team. How much do I get for an outstation recruitment drive on a non-working day?"`
   Point at: group = technical *(inferred from the question)* before retrieval; **₹1000/day**; citation names **Revision 11 (June 2025) · PDF p.26** with a link; trace id; cost and the model / tools split.
2. `python capstone/capstone.py ask "I worked 8 hours on a company holiday. What compensation do I get?" --group non_technical` → one day of compensatory off; **no ₹500 / ₹1000** (suite case G09, which failed before the fix). This is the group analog of "a v2.4 caller never gets a v3 snippet".
3. `python capstone/capstone.py ask "What is the paternity leave policy?"` → "That is not covered in the Employee Handbook." Said plainly, no invented policy.
4. Not "how do I authenticate": use a question where the groups differ (leave carry-forward, hours, holiday pay).

## Part 2: the failures (3 min)
- Open trace `tr_625df6fe1693` (G07, pre-fix): the agent searched 3×, never saw ₹1000, blew the 12,000-token budget. Root cause: chunk_57 opens with the technical rule's tail but was tagged non-technical.
- TAXONOMY.md: 7 modes with frequencies. The three NEW ones created by integration: chunk-boundary group bleed (10/10 and 8/8), null `employee_group` rejected by Groq (4/30 = 13%), revision guard overwriting a correct answer (R03).
- WEAKNESSES.md (dated 2026-10-30): judge at 75%, citation precision, leftover tail leak (10/10).

## Part 3: a number that moved (2 min)
- `python capstone/measure_group_tagging.py` table: technical miss **10/10 → 0/10**, non-technical bleed **8/8 → 0/8**. n=10 and n=8, deterministic.
- Suite: 4/13 (31%) before → 25/28 (89%) valid after. Say out loud that 2 of the recovered cases were my own assertion bug and 2 of 30 rows are excluded for the Groq quota.
- Judge agreement **75% (21/28)**, below 85%, against labels that are drafts until confirmed. 4 of 7 misses = the judge never saw the revision register (fixed, unmeasured).
- What the suite does not measure: **run-to-run variance** (one run per case) and **citation precision**.

## Part 4: what's next (2 min)
- The permanent guard: eval cases G06/G07/G09 (+ `measure_group_tagging.py`) for group bleed; R03 for the guard; selftest asserts for "₹1,000", "chunk 56", "chunks 17 and 19", "Revisions 9".
- Cost: **$0.000429 per question**, 4,447 tokens.
- 10×: the **200,000 tokens/day** cap = about 45 questions a day; 10× today is 6.7× over it. Cost at 18,000 q/day is ≈ $7.7. See COST_AND_10X.md.

## Closed failure→test loop (do this live if asked)
Failing test first: `python capstone/capstone.py eval --only R03-rev9-10` on the old guard regex (`revision\s*\d+`) goes red; the selftest assert `enforce_revision_authority("When were Revisions 9 and 10 issued?", ...)` is the offline version of the same case. Fix = `revisions?\s*\d+`. Green again; run the full selftest to show no other case moved.
