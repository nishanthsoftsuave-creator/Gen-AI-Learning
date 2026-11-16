"""Trajectory eval on the INTEGRATED agent (Week 8 method, same definitions, no extra API calls).

Reads the tool calls the agent actually made in the last `capstone.py eval` run (they are in each
trace file) and scores them against the expected paths below.

EXPECTED was frozen on 2026-10-30, before the post-fix eval run had finished its first cases.

  outcome pass     the case's deterministic assertions passed (eval_integrated.check)
  tool_choice pass some expected path is fully covered by the agent's successful calls
  trajectory pass  tool_choice pass AND no tool outside the expected set AND no invalid argument
  gap              outcome pass rate - trajectory pass rate (percentage points)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "Agentic Ai"), str(HERE.parent / "src")]
from trajectory_eval import validate_arguments  # noqa: E402  (the Week 8 schema rules)

RESULTS_FILE = HERE / "output" / "eval_results.jsonl"
OUT_FILE = HERE / "output" / "trajectory_integrated.json"

SEARCH = [{"tool": "search_handbook"}]
REVISIONS = [{"tool": "get_handbook_revisions"}]


def section(name):
    return [{"tool": "get_policy_section", "section": name}]


COMPENSATION = section("work_from_home_and_deputation_compensation")
# case id -> alternative paths (any one satisfies tool choice)
EXPECTED = {
    "G01-tech-leave": [SEARCH], "G02-nontech-leave": [SEARCH], "G03-unresolved-leave": [SEARCH],
    "G04-tech-hours": [SEARCH], "G05-nontech-hours": [SEARCH],
    "G06-tech-recruit-both": [SEARCH, COMPENSATION], "G07-tech-recruit-outstation": [SEARCH, COMPENSATION],
    "G08-tech-newproject": [SEARCH, COMPENSATION], "G09-nontech-holiday": [SEARCH, COMPENSATION],
    "G10-unresolved-compare": [SEARCH, COMPENSATION],
    "L01-hr-contact": [section("contact_details"), SEARCH], "L02-leadership": [section("company_leadership"), SEARCH],
    "L03-leave-entitlement": [SEARCH], "L04-notice-period": [SEARCH], "L05-dress-code": [SEARCH],
    "L06-maternity": [SEARCH], "L07-sandwich": [SEARCH], "L08-pf-timing": [SEARCH], "L09-leave-in-notice": [SEARCH],
    "L10-discipline": [section("disciplinary_actions"), SEARCH],
    "L11-misconduct-contact": [section("employee_code_of_conduct") + section("disciplinary_actions"), SEARCH],
    "R01-latest-revision": [REVISIONS], "R02-rev6-legacy": [REVISIONS], "R03-rev9-10": [REVISIONS],
    "R04-kept-current": [REVISIONS, SEARCH],
    "N01-paternity": [SEARCH], "N02-gratuity": [SEARCH], "N03-esop": [SEARCH], "N04-insurance": [SEARCH],
    "P01-pasted-secrets": [SEARCH],
}


def key(tool, arguments):
    return (tool, (arguments or {}).get("section") if tool == "get_policy_section" else None)


def score(case_id, tool_calls):
    paths = EXPECTED[case_id]
    ok = [c for c in tool_calls if c["error"] is None]
    done = {key(c["tool"], c["arguments"]) for c in ok}
    path_keys = [{key(s["tool"], s) for s in p} for p in paths]
    allowed = set().union(*path_keys)
    tool_choice = any(p <= done for p in path_keys)
    wrong = [c["tool"] for c in ok if key(c["tool"], c["arguments"]) not in allowed]
    invalid = []
    for c in tool_calls:
        # employee_group is overwritten by code (tools.dispatch_tool), so the model's value never matters
        args = {k: v for k, v in (c["arguments"] or {}).items() if k != "employee_group"}
        valid, reason = validate_arguments(c["tool"], args)
        if c["error"] is not None or not valid:
            invalid.append(c["error"] or reason)
    min_steps = min(len(p) for p in paths)
    return {"tool_choice": tool_choice, "wrong_tools": wrong, "invalid_args": invalid, "steps": len(tool_calls),
            "min_steps": min_steps, "trajectory": tool_choice and not wrong and not invalid}


def main():
    rows, skipped = [], []
    for line in RESULTS_FILE.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["termination"].startswith("ERROR:APIStatus") or r["rate_limit_wait_s"] > 60:
            skipped.append(r["id"])  # Groq daily quota, not the agent: no valid trajectory
            continue
        trace = json.loads(Path(r["trace_file"]).read_text(encoding="utf-8"))
        rows.append({"id": r["id"], "mode": r["mode"], "outcome": r["passed"], "termination": r["termination"],
                     "calls": [c["tool"] for c in trace["tool_calls"]], **score(r["id"], trace["tool_calls"])})
    n = len(rows)
    rate = lambda f: sum(1 for r in rows if f(r)) / n  # noqa: E731
    summary = {"n": n, "skipped_quota": skipped, "outcome_pass": rate(lambda r: r["outcome"]), "tool_choice_accuracy": rate(lambda r: r["tool_choice"]),
               "trajectory_pass": rate(lambda r: r["trajectory"]),
               "gap_pp": (rate(lambda r: r["outcome"]) - rate(lambda r: r["trajectory"])) * 100,
               "right_answer_wrong_path": [r["id"] for r in rows if r["outcome"] and not r["trajectory"]],
               "wrong_answer_right_path": [r["id"] for r in rows if not r["outcome"] and r["trajectory"]],
               "excess_steps_cases": [r["id"] for r in rows if r["steps"] > r["min_steps"] + 1]}
    OUT_FILE.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    for r in rows:
        print(f"{r['id']:<28} outcome={r['outcome']!s:<5} tool_choice={r['tool_choice']!s:<5} traj={r['trajectory']!s:<5} "
              f"steps={r['steps']} calls={r['calls']} wrong={r['wrong_tools']} invalid={len(r['invalid_args'])}")


def selftest():
    hr = {"tool": "get_handbook_revisions", "arguments": {}, "error": None}
    search = {"tool": "search_handbook", "arguments": {"query": "x", "employee_group": "technical"}, "error": None}
    assert score("R01-latest-revision", [hr])["trajectory"]
    assert not score("R01-latest-revision", [search])["tool_choice"]
    assert score("G01-tech-leave", [search, hr])["wrong_tools"] == ["get_handbook_revisions"]  # right tool + a wrong one
    assert score("G01-tech-leave", [search])["trajectory"]  # model-supplied employee_group is not an invalid argument
    assert not score("G01-tech-leave", [{**search, "error": "boom"}])["trajectory"]


if __name__ == "__main__":
    selftest() if sys.argv[1:] == ["selftest"] else main()
