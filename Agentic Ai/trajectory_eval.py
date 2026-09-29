"""Week 8 Step 3 -- BASELINE trajectory evaluation for the dynamic Employee
Handbook agent (agent.py), scored against the trajectory ground truth frozen
in Week 8 Step 2.

This script does not modify agent.py, workflow.py, tools.py, budgets.py, or
race_questions.json, and does not change agent behavior in any way. It runs
the EXISTING agent (agent.py::run_agent) unmodified against the EXISTING 10
questions (race_questions.json), reuses the EXISTING outcome evaluator
(race.py::evaluate) for outcome_pass, and reuses the EXISTING trace/token/
cost infrastructure (agent_tracing.py, budgets.py, cost.py) for the cost
metrics below. It adds a new, additive layer: tool-choice accuracy, argument
validity, step efficiency, and the outcome-vs-trajectory gap.

TRACE LIMITATION (carried over from Week 8 Step 1's inspection): the existing
trace schema (agent_tracing.py::save_run_trace) persists tool NAME +
ARGUMENTS + error for each call, but NOT the tool's output/evidence. This
script therefore cannot and does not score "did the agent look at evidence
that actually contained the answer" -- only "did the agent call a tool/
argument combination that the Week 8 Step 2 ground truth verified DOES
contain the answer, for this exact question". Tool-choice and argument
validity below are computed entirely from {tool, arguments, error} as
already recorded by agent.py's live dispatch_tool() calls during this run.
No tool is re-executed or re-queried by this script for any of the 10
questions -- the ground truth in TRAJECTORY_CASES below already encodes,
per question, which tool/argument combinations were verified (in Step 2, by
directly calling search_handbook/get_policy_section/get_handbook_revisions
and reading raw chunk text) to actually contain the required facts.

Run: python trajectory_eval.py
"""

import csv
import json
import re
import statistics
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from agent import run_agent
from race import evaluate, QUESTIONS_FILE
from tools import SUPPORTED_SECTIONS

AGENTIC_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = AGENTIC_DIR / "output"
BASELINE_JSON = OUTPUT_DIR / "trajectory_baseline.json"
BASELINE_CSV = OUTPUT_DIR / "trajectory_baseline.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TRACE_LIMITATION_NOTE = (
    "Existing trace schema (agent_tracing.py) does not persist tool outputs, "
    "only {tool, arguments, error}. Tool-choice / argument-validity scoring "
    "below is computed solely from that logged call data plus the Step 2 "
    "ground truth (which was independently verified against raw handbook "
    "chunks in Step 2, not re-verified here). No tool was re-executed by "
    "this script; this script only calls agent.py::run_agent once per "
    "question, exactly as race.py does for the agent side of the race."
)

WALL_CLOCK_CONFOUND_NOTE = (
    "elapsed_seconds includes any time spent in llm_client.py's Groq 429 "
    "retry backoff (visible on stdout as '[llm_client] rate limited, "
    "retrying in Ns'). This is a known, external, shared confound (see "
    "Agentic Ai/README.md 'Limitations') and is reported as-is below, not "
    "corrected for."
)


# ---------------------------------------------------------------------------
# Week 8 Step 2 trajectory ground truth (frozen before this baseline ran)
# ---------------------------------------------------------------------------
# Each expected path is a list of steps; each step is either:
#   {"tool": "search_handbook"}            -- any valid arguments accepted
#   {"tool": "get_handbook_revisions"}     -- no arguments
#   {"tool": "get_policy_section", "section": "<one of SUPPORTED_SECTIONS>"}
#
# "insufficient_single_tool_traps" (Q6 only): a set of steps that LOOK like a
# complete, correct single-tool answer but were verified in Step 2 to be
# structurally insufficient regardless of agent skill (a tool/section-
# labeling defect, not a reasoning failure). Used only for diagnostic
# labeling (correct_tool_insufficient_evidence), never to fail tool_choice.

TRAJECTORY_CASES = {
    "Q1": {
        "expected_paths": [
            [{"tool": "get_policy_section", "section": "company_leadership"}],
            [{"tool": "search_handbook"}],
        ],
        "min_steps": 1,
        "dependency": False,
        "week5_failure_mode": "separate_people_presented_as_one_role_holder",
        "notes": (
            "Trajectory can be fully correct and the outcome can still fail: "
            "chunk_99 (returned by both paths) renders the two names with no "
            "separator ('RAMESH VAYAVURU MANOHAR VAYYAVURU')."
        ),
    },
    "Q2": {
        "expected_paths": [
            [{"tool": "get_handbook_revisions"}],
        ],
        "min_steps": 1,
        "dependency": False,
        "week5_failure_mode": "answer_declares_info_unavailable_despite_related_material",
        "notes": (
            "search_handbook is NOT a legitimate alternate path -- verified "
            "empirically in Step 2: the revision-list chunk only ranks in "
            "the top 8 (at position 8) for the natural question phrasing, "
            "never in a realistic top_k."
        ),
    },
    "Q3": {
        "expected_paths": [
            [
                {"tool": "get_policy_section", "section": "employee_code_of_conduct"},
                {"tool": "get_policy_section", "section": "disciplinary_actions"},
            ],
            [
                {"tool": "get_policy_section", "section": "disciplinary_actions"},
                {"tool": "get_policy_section", "section": "employee_code_of_conduct"},
            ],
        ],
        "min_steps": 2,
        "dependency": True,
        "week5_failure_mode": None,
        "notes": (
            "Verified in Step 2: chunk_85 (code_of_conduct) ends before "
            "consequences are stated; chunk_97 (disciplinary_actions) is the "
            "only chunk with 'reprimand, suspension or termination'."
        ),
    },
    "Q4": {
        "expected_paths": [
            [{"tool": "get_policy_section", "section": "work_from_home_and_deputation_compensation"}],
            [{"tool": "search_handbook"}],
        ],
        "min_steps": 1,
        "dependency": False,
        "week5_failure_mode": None,
        "notes": None,
    },
    "Q5": {
        "expected_paths": [
            [
                {"tool": "get_handbook_revisions"},
                {"tool": "get_policy_section", "section": "contact_details"},
            ],
            [
                {"tool": "get_policy_section", "section": "contact_details"},
                {"tool": "get_handbook_revisions"},
            ],
        ],
        "min_steps": 2,
        "dependency": True,
        "week5_failure_mode": "answer_declares_info_unavailable_despite_related_material",
        "notes": (
            "Verified in Step 2: chunk_29/chunk_31 (contact_details tool's "
            "actual output for this anchor) both contain 'teamhr@softsuave.com', "
            "so contact_details IS reliable for the email half here."
        ),
    },
    "Q6": {
        "expected_paths": [
            [
                {"tool": "get_policy_section", "section": "contact_details"},
                {"tool": "get_policy_section", "section": "disciplinary_actions"},
            ],
            [
                {"tool": "get_policy_section", "section": "disciplinary_actions"},
                {"tool": "get_policy_section", "section": "contact_details"},
            ],
        ],
        "min_steps": 2,
        "dependency": True,
        "week5_failure_mode": "answer_declares_info_unavailable_despite_related_material",
        "insufficient_single_tool_traps": [
            [{"tool": "get_policy_section", "section": "contact_details"}],
        ],
        "notes": (
            "NOT a simple_lookup despite race_questions.json's "
            "requires_dependency=false. Verified in Step 2: "
            "get_policy_section('contact_details') anchor 'teamhr@softsuave.com' "
            "matches 6 chunks (29,31,54,55,56,97); the tool keeps only the "
            "first two in chunk-id order (29,31), which never contain "
            "'sudhendra'. The real Contact Details section body (with the "
            "HRM name) is chunk_97, labeled 'disciplinary_actions' by the "
            "tool's own section taxonomy. search_handbook does not reliably "
            "rescue this either (chunk_97 only appears at top_k>=8 with a "
            "reformulated query, never with the natural question at "
            "realistic top_k). This is a tool/section-labeling defect, not "
            "an agent reasoning failure -- do not fix in this step."
        ),
    },
    "Q7": {
        "expected_paths": [
            [{"tool": "get_policy_section", "section": "disciplinary_actions"}],
            [{"tool": "search_handbook"}],
        ],
        "min_steps": 1,
        "dependency": False,
        "week5_failure_mode": None,
        "notes": None,
    },
    "Q8": {
        "expected_paths": [
            [{"tool": "search_handbook"}, {"tool": "get_handbook_revisions"}],
            [{"tool": "get_handbook_revisions"}, {"tool": "search_handbook"}],
        ],
        "min_steps": 2,
        "dependency": True,
        "week5_failure_mode": None,
        "notes": (
            "search_handbook (chunk_4/5) carries the 'agreed to be bound' "
            "acceptance language; the exact modifications-clause wording is "
            "authoritative only via get_handbook_revisions."
        ),
    },
    "Q9": {
        "expected_paths": [
            [{"tool": "get_policy_section", "section": "work_from_home_and_deputation_compensation"}],
            [{"tool": "search_handbook"}],
        ],
        "min_steps": 1,
        "dependency": False,
        "week5_failure_mode": None,
        "notes": "Same underlying section/chunk as Q4 (chunk_57).",
    },
    "Q10": {
        "expected_paths": [
            [
                {"tool": "get_policy_section", "section": "company_leadership"},
                {"tool": "get_handbook_revisions"},
            ],
            [
                {"tool": "get_handbook_revisions"},
                {"tool": "get_policy_section", "section": "company_leadership"},
            ],
            [{"tool": "search_handbook"}, {"tool": "get_handbook_revisions"}],
        ],
        "min_steps": 2,
        "dependency": True,
        "week5_failure_mode": "separate_people_presented_as_one_role_holder",
        "notes": "Combines Q1's name-merging risk and Q2's revision-count risk.",
    },
}


# ---------------------------------------------------------------------------
# Argument validity (schema-based; no tool re-execution)
# ---------------------------------------------------------------------------

_VERSION_LIKE = re.compile(r"\bv\d+(\.\d+)?\b|\bversion\s*\d+\b", re.IGNORECASE)


def validate_arguments(tool, arguments):
    """Schema-based argument validation using the SAME rules tools.py's
    TOOL_SCHEMAS declare -- does not execute the tool. Returns (is_valid,
    reason_or_None)."""

    arguments = arguments or {}

    if tool == "search_handbook":
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            return False, "query missing or empty"
        if _VERSION_LIKE.search(query):
            return False, (
                "query references a 'version' string (e.g. v2/version 3) -- "
                "this domain has no policy versions, only dated revisions "
                "(get_handbook_revisions); do not invent version strings"
            )
        if "top_k" in arguments:
            top_k = arguments["top_k"]
            if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
                return False, f"top_k must be a positive integer, got {top_k!r}"
        extra = set(arguments) - {"query", "top_k"}
        if extra:
            return False, f"unexpected extra arguments: {sorted(extra)}"
        return True, None

    if tool == "get_policy_section":
        if "section" not in arguments:
            return False, "missing required 'section' argument"
        section = arguments["section"]
        if section not in SUPPORTED_SECTIONS:
            return False, f"section {section!r} is not one of the 8 supported sections"
        extra = set(arguments) - {"section"}
        if extra:
            return False, f"unexpected extra arguments: {sorted(extra)}"
        return True, None

    if tool == "get_handbook_revisions":
        if arguments:
            return False, f"get_handbook_revisions takes no arguments, got {arguments}"
        return True, None

    return False, f"unknown tool {tool!r}"


# ---------------------------------------------------------------------------
# Trajectory scoring
# ---------------------------------------------------------------------------

def _call_key(tool, arguments):
    if tool == "get_policy_section":
        return ("get_policy_section", (arguments or {}).get("section"))
    return (tool, None)


def _path_keys(path):
    return {_call_key(step["tool"], step) for step in path}


def score_trajectory(question_id, tool_calls):
    """Scores one question's actual tool_calls (from a fresh run_agent()
    result) against TRAJECTORY_CASES[question_id]. Returns a dict with every
    field needed for the per-question report row."""

    case = TRAJECTORY_CASES[question_id]
    expected_paths = case["expected_paths"]
    min_steps = case["min_steps"]

    # --- argument validity (every call, regardless of relevance) ---
    invalid_argument_cases = []
    arg_valid_flags = []
    for call in tool_calls:
        dispatch_ok = call["error"] is None
        static_ok, reason = validate_arguments(call["tool"], call["arguments"])
        is_valid = dispatch_ok and static_ok
        arg_valid_flags.append(is_valid)
        if not is_valid:
            invalid_argument_cases.append(
                {
                    "question_id": question_id,
                    "iteration": call["iteration"],
                    "tool": call["tool"],
                    "arguments": call["arguments"],
                    "reason": call["error"] if not dispatch_ok else reason,
                    "source": "dispatch_error" if not dispatch_ok else "schema_check",
                }
            )
    argument_validity_rate = (
        sum(arg_valid_flags) / len(arg_valid_flags) if arg_valid_flags else None
    )
    argument_valid_count = sum(arg_valid_flags)
    argument_total_count = len(arg_valid_flags)

    # --- tool-choice: which expected path(s), if any, are satisfied ---
    successful_calls = [c for c in tool_calls if c["error"] is None]
    successful_keys_in_order = [_call_key(c["tool"], c["arguments"]) for c in successful_calls]
    successful_key_set = set(successful_keys_in_order)

    matched_paths = [p for p in expected_paths if _path_keys(p) <= successful_key_set]
    tool_choice_pass = bool(matched_paths)

    if matched_paths:
        best_path = min(matched_paths, key=len)
        missing_required = []
    else:
        # report the closest expected path (fewest missing keys) for diagnosis
        best_path = min(expected_paths, key=lambda p: len(_path_keys(p) - successful_key_set))
        missing_required = sorted(
            f"{t}:{s}" if s else t for (t, s) in (_path_keys(best_path) - successful_key_set)
        )

    union_keys = set()
    for p in expected_paths:
        union_keys |= _path_keys(p)

    wrong_tool_calls = []
    unnecessary_calls = []
    search_loop_calls = []
    seen_keys = set()
    search_handbook_seen = False
    for call, key in zip(successful_calls, successful_keys_in_order):
        if key not in union_keys:
            wrong_tool_calls.append(call)
            continue
        if key[0] == "search_handbook":
            if search_handbook_seen:
                search_loop_calls.append(call)
                continue
            search_handbook_seen = True
        if key in seen_keys:
            unnecessary_calls.append(call)
        else:
            seen_keys.add(key)

    # correct_tool_insufficient_evidence: an actual call matched a known trap
    # (a plausible-looking single-tool answer verified in Step 2 to be
    # structurally insufficient), and the question was not otherwise solved.
    insufficient_evidence_trap_hit = False
    for trap in case.get("insufficient_single_tool_traps", []):
        if _path_keys(trap) <= successful_key_set and not tool_choice_pass:
            insufficient_evidence_trap_hit = True

    actual_steps = len(tool_calls)
    step_efficiency = actual_steps / min_steps if min_steps else None

    failure_modes = []
    if not tool_choice_pass:
        if insufficient_evidence_trap_hit:
            failure_modes.append("correct_tool_insufficient_evidence")
        else:
            failure_modes.append("missing_required_tool")
    if wrong_tool_calls:
        failure_modes.append("wrong_tool")
    if unnecessary_calls:
        failure_modes.append("unnecessary_tool")
    if search_loop_calls:
        failure_modes.append("search_loop")
    if invalid_argument_cases:
        failure_modes.append("invalid_arguments")
    if step_efficiency is not None and step_efficiency > 1.0:
        failure_modes.append("excessive_steps")

    # trajectory_pass: the agent used a legitimate tool/argument combination
    # covering every fact the question needs, called nothing irrelevant, and
    # made no invalid-argument calls. Redundant repeats (unnecessary_tool /
    # search_loop) are an efficiency issue, tracked separately, and do not
    # by themselves fail trajectory_pass.
    trajectory_pass = tool_choice_pass and not wrong_tool_calls and not invalid_argument_cases

    week5_mapping = case["week5_failure_mode"] if failure_modes else None

    return {
        "expected_paths": expected_paths,
        "best_matched_or_closest_path": best_path,
        "missing_required": missing_required,
        "tool_choice_pass": tool_choice_pass,
        "argument_validity_rate": argument_validity_rate,
        "invalid_argument_cases": invalid_argument_cases,
        "argument_valid_count": argument_valid_count,
        "argument_total_count": argument_total_count,
        "actual_steps": actual_steps,
        "min_steps": min_steps,
        "step_efficiency": step_efficiency,
        "wrong_tool_calls": [c["tool"] for c in wrong_tool_calls],
        "unnecessary_calls": [c["tool"] for c in unnecessary_calls],
        "search_loop_calls": [c["tool"] for c in search_loop_calls],
        "failure_modes": failure_modes,
        "week5_failure_mode": week5_mapping,
        "trajectory_pass": trajectory_pass,
        "dependency": case["dependency"],
        "notes": case["notes"],
    }


def _format_path(tool_calls):
    out = []
    for c in tool_calls:
        if c["tool"] == "get_policy_section":
            out.append(f"get_policy_section:{(c['arguments'] or {}).get('section')}")
        else:
            out.append(c["tool"])
    return out


def _format_expected(path):
    out = []
    for step in path:
        if step["tool"] == "get_policy_section":
            out.append(f"get_policy_section:{step['section']}")
        else:
            out.append(step["tool"])
    return out


# ---------------------------------------------------------------------------
# Main baseline run
# ---------------------------------------------------------------------------

def run_baseline():
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    missing_ids = [q["id"] for q in questions if q["id"] not in TRAJECTORY_CASES]
    if missing_ids:
        raise RuntimeError(
            f"TRAJECTORY_CASES is missing ground truth for question id(s): {missing_ids}. "
            "Refusing to guess -- extend TRAJECTORY_CASES first."
        )

    rows = []
    invalid_argument_cases_all = []
    right_answer_wrong_path = []
    total_arg_valid = 0
    total_arg_calls = 0

    for q in questions:
        qid = q["id"]
        print(f"[trajectory_eval] running agent :: {qid}")
        result = run_agent(q["question"], question_id=qid)

        outcome_pass, outcome_detail = evaluate(result["answer"], q)
        traj = score_trajectory(qid, result["tool_calls"])

        row = {
            "question_id": qid,
            "question": q["question"],
            "outcome_pass": outcome_pass,
            "trajectory_pass": traj["trajectory_pass"],
            "expected_path": " OR ".join(
                "->".join(_format_expected(p)) for p in traj["expected_paths"]
            ),
            "actual_path": "->".join(_format_path(result["tool_calls"])),
            "tool_choice_accuracy": traj["tool_choice_pass"],
            "argument_validity": f"{traj['argument_valid_count']}/{traj['argument_total_count']}",
            "actual_steps": traj["actual_steps"],
            "minimum_steps": traj["min_steps"],
            "step_efficiency": round(traj["step_efficiency"], 3) if traj["step_efficiency"] is not None else None,
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "total_tokens": result["total_tokens"],
            "cost": result["cost"],
            "elapsed_seconds": round(result["elapsed_seconds"], 3),
            "termination_reason": result["termination_reason"],
            "failure_modes": traj["failure_modes"],
            "week5_failure_mode": traj["week5_failure_mode"],
            "dependency": traj["dependency"],
            "missing_required": traj["missing_required"],
            "wrong_tool_calls": traj["wrong_tool_calls"],
            "unnecessary_calls": traj["unnecessary_calls"],
            "search_loop_calls": traj["search_loop_calls"],
            "trace_id": result["trace_id"],
            "trace_file": result["trace_file"],
        }
        rows.append(row)
        invalid_argument_cases_all.extend(traj["invalid_argument_cases"])
        total_arg_valid += traj["argument_valid_count"]
        total_arg_calls += traj["argument_total_count"]

        if outcome_pass and not traj["trajectory_pass"]:
            right_answer_wrong_path.append(
                {
                    "question_id": qid,
                    "question": q["question"],
                    "expected_paths": [_format_expected(p) for p in traj["expected_paths"]],
                    "actual_path": _format_path(result["tool_calls"]),
                    "outcome_result": "PASS",
                    "trajectory_failure_reason": traj["failure_modes"],
                    "missing_required": traj["missing_required"],
                }
            )

        print(
            f"    outcome_pass={outcome_pass} trajectory_pass={traj['trajectory_pass']} "
            f"steps={traj['actual_steps']}/{traj['min_steps']} "
            f"failure_modes={traj['failure_modes']} termination={result['termination_reason']}"
        )

    # --- overall metrics ---
    n = len(rows)
    outcome_pass_rate = sum(1 for r in rows if r["outcome_pass"]) / n
    trajectory_pass_rate = sum(1 for r in rows if r["trajectory_pass"]) / n
    gap_pp = (outcome_pass_rate - trajectory_pass_rate) * 100

    tool_choice_accuracy = sum(1 for r in rows if r["tool_choice_accuracy"]) / n

    argument_validity_rate_overall = total_arg_valid / total_arg_calls if total_arg_calls else None

    efficiencies = [r["step_efficiency"] for r in rows if r["step_efficiency"] is not None]
    costs = [r["cost"] for r in rows]

    failure_taxonomy = {
        "wrong_tool": 0,
        "missing_required_tool": 0,
        "unnecessary_tool": 0,
        "invalid_arguments": 0,
        "excessive_steps": 0,
        "search_loop": 0,
        "correct_tool_insufficient_evidence": 0,
        "other": 0,
    }
    for r in rows:
        for mode in r["failure_modes"]:
            if mode in failure_taxonomy:
                failure_taxonomy[mode] += 1
        if r["termination_reason"] != "COMPLETED" and not r["failure_modes"]:
            failure_taxonomy["other"] += 1

    summary = {
        "n_questions": n,
        "outcome_pass_rate": outcome_pass_rate,
        "trajectory_pass_rate": trajectory_pass_rate,
        "outcome_trajectory_gap_pp": gap_pp,
        "tool_choice_accuracy": tool_choice_accuracy,
        "argument_validity_rate_overall": argument_validity_rate_overall,
        "step_efficiency_p50": statistics.median(efficiencies) if efficiencies else None,
        "step_efficiency_max": max(efficiencies) if efficiencies else None,
        "cost_p50": statistics.median(costs) if costs else None,
        "cost_max": max(costs) if costs else None,
        "cost_mean": statistics.mean(costs) if costs else None,
        "failure_taxonomy": failure_taxonomy,
        "right_answer_wrong_path_count": len(right_answer_wrong_path),
    }

    output = {
        "meta": {
            "trace_limitation": TRACE_LIMITATION_NOTE,
            "wall_clock_confound": WALL_CLOCK_CONFOUND_NOTE,
            "system_under_test": "agent (agent.py::run_agent) only -- workflow.py is a fixed pipeline with no tool-choice to score",
        },
        "summary": summary,
        "per_question": rows,
        "invalid_argument_cases": invalid_argument_cases_all,
        "right_answer_wrong_path": right_answer_wrong_path,
    }

    BASELINE_JSON.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    csv_fields = [
        "question_id", "outcome_pass", "trajectory_pass", "expected_path", "actual_path",
        "tool_choice_accuracy", "argument_validity", "actual_steps", "minimum_steps",
        "step_efficiency", "input_tokens", "output_tokens", "total_tokens", "cost",
        "elapsed_seconds", "termination_reason", "failure_modes", "week5_failure_mode",
    ]
    with BASELINE_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            row_out = dict(r)
            row_out["failure_modes"] = ";".join(r["failure_modes"])
            writer.writerow(row_out)

    _print_report(rows, summary, right_answer_wrong_path)

    print(f"\nWrote {BASELINE_JSON}")
    print(f"Wrote {BASELINE_CSV}")

    return output


def _print_report(rows, summary, right_answer_wrong_path):
    print("\n" + "=" * 100)
    print("A. PER-QUESTION RESULTS")
    print("=" * 100)
    header = (
        f"{'ID':<4}{'Outcome':<9}{'Traj':<7}{'Steps':<8}{'Eff':<7}"
        f"{'Tokens':<9}{'Cost':<11}{'Elapsed':<10}{'Failure modes'}"
    )
    print(header)
    for r in rows:
        print(
            f"{r['question_id']:<4}"
            f"{str(r['outcome_pass']):<9}"
            f"{str(r['trajectory_pass']):<7}"
            f"{str(r['actual_steps']) + '/' + str(r['minimum_steps']):<8}"
            f"{(str(r['step_efficiency']) if r['step_efficiency'] is not None else '-'):<7}"
            f"{r['total_tokens']:<9}"
            f"{'$' + format(r['cost'], '.6f'):<11}"
            f"{format(r['elapsed_seconds'], '.2f') + 's':<10}"
            f"{','.join(r['failure_modes']) or '-'}"
        )
        print(f"     expected: {r['expected_path']}")
        print(f"     actual:   {r['actual_path'] or '(none)'}")

    print("\n" + "=" * 100)
    print("B. OVERALL METRICS")
    print("=" * 100)
    print(f"Outcome pass rate:        {summary['outcome_pass_rate'] * 100:.0f}%")
    print(f"Trajectory pass rate:     {summary['trajectory_pass_rate'] * 100:.0f}%")
    print(f"Outcome-trajectory gap:   {summary['outcome_trajectory_gap_pp']:.1f} percentage points")
    print(f"Tool-choice accuracy:     {summary['tool_choice_accuracy'] * 100:.0f}%")
    rate = summary["argument_validity_rate_overall"]
    print(f"Argument validity rate:   {rate * 100:.0f}%" if rate is not None else "Argument validity rate:   n/a")
    print("Step efficiency:")
    print(f"  p50: {summary['step_efficiency_p50']:.2f}" if summary["step_efficiency_p50"] is not None else "  p50: n/a")
    print(f"  max: {summary['step_efficiency_max']:.2f}" if summary["step_efficiency_max"] is not None else "  max: n/a")
    print("Cost (USD per question):")
    print(f"  p50:  ${summary['cost_p50']:.6f}")
    print(f"  max:  ${summary['cost_max']:.6f}")
    print(f"  mean: ${summary['cost_mean']:.6f}  (reported for context -- p50/max are the required figures)")

    print("\n" + "=" * 100)
    print("C. FAILURE-MODE COUNTS (questions exhibiting each mode at least once)")
    print("=" * 100)
    for mode, count in summary["failure_taxonomy"].items():
        print(f"  {mode:<35} {count}")

    print("\n" + "=" * 100)
    print("D. RIGHT-ANSWER / WRONG-PATH CASES (outcome_pass=True, trajectory_pass=False)")
    print("=" * 100)
    if not right_answer_wrong_path:
        print("  None in this run.")
    else:
        for case in right_answer_wrong_path:
            print(f"  {case['question_id']}: {case['question']}")
            print(f"    expected path(s): {case['expected_paths']}")
            print(f"    actual path:      {case['actual_path']}")
            print(f"    outcome:          {case['outcome_result']}")
            print(f"    trajectory failure reason: {case['trajectory_failure_reason']}")
            if case["missing_required"]:
                print(f"    missing required: {case['missing_required']}")

    print("\n" + "=" * 100)
    print("NOTES")
    print("=" * 100)
    print(f"  {TRACE_LIMITATION_NOTE}")
    print(f"  {WALL_CLOCK_CONFOUND_NOTE}")


if __name__ == "__main__":
    run_baseline()
