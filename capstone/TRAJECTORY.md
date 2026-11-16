# Trajectory eval on the integrated agent

`python capstone/trajectory_integrated.py` (no API calls; reads the tool calls from the last eval run's traces). Expected paths are frozen in the script, written 2026-10-30 before the post-fix run had finished its first cases. Week 8 definitions: tool-choice = an expected path is fully covered by successful calls; trajectory = tool-choice, no tool outside the expected set, no invalid argument; gap = outcome pass rate minus trajectory pass rate.

**n = 28** (L01 and N02 excluded: Groq daily quota, no valid trajectory).

| Metric | Integrated agent (n=28) | Week 8 baseline for reference (n=10, different cases) |
|---|---:|---:|
| Outcome pass (assertions) | 89.3% (25/28) | 60% → 90% after mitigation |
| **Tool-choice accuracy** | **92.9% (26/28)** | 60% → 70% |
| Trajectory pass | 78.6% (22/28) | 30% → 40% |
| **Outcome-vs-trajectory gap** | **10.7 pp** | 30 → 50 pp |

The gap is smaller than Week 8's, but do not read that as "the agent got better at reasoning": the case sets differ, n went from 10 to 28, and these expected paths allow alternatives (`search_handbook` *or* the named section). The comparison is context, not a result.

## Where outcome and trajectory disagree (5 right answers, wrong path)

| Case | What happened |
|---|---|
| L11-misconduct-contact | Called only `employee_code_of_conduct`, never `disciplinary_actions`. The answer still contained the consequences, so the assertion passed. |
| R01, R02, R03 | Correct tool, but the model passed `{"": ""}` to a zero-argument tool. Week 8's validator counts it invalid (the dispatcher quietly normalises it, so users never see it). |
| **N03-esop** | **Zero tool calls.** "That is not covered in the Employee Handbook." came from the model, not from a search. Outcome green, no evidence behind it. This is the one that embarrasses me: an outcome-only grader cannot tell a checked refusal from a guessed one. |

Opposite direction (2 wrong outcomes on the right path): G04 and L08 are guard-flagged answers. One right path was legitimately used and a derived/restated figure tripped the guard.

Also: L05 called `get_policy_section` (outside its expected set), so its trajectory fails even though its answer's content is supported.

Steps: no case used more than min steps + 1. Mean 1.14 tool calls per question.
