"""Integrated eval suite: every case goes through capstone.ask() (RAG + agent + MCP + guards + logging).

Assertions decide pass/fail (deterministic). The LLM judge only scores faithfulness and is advisory;
its agreement with hand labels is computed from judge_labels.csv (`python eval_integrated.py agreement`).
"""
import csv
import json
import re
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES_FILE = HERE / "eval_cases.jsonl"
OUT = HERE / "output"
RESULTS_FILE = OUT / "eval_results.jsonl"
LABELS_FILE = HERE / "judge_labels.csv"
SUMMARY_FILE = HERE / "eval_summary.md"
NOT_COVERED = re.compile(
    r"not (?:covered|mentioned|specified|included|addressed|available|found|stated|part)|"
    r"no (?:information|mention|details|policy|provision)|"
    r"(?:does not|doesn't|do not|don't|cannot|can't|could not|couldn't) (?:contain|include|cover|mention|specify|provide|find|address)",
    re.I,
)


def _norm(text):
    text = (text or "").replace(" ", " ").replace(" ", " ").replace("–", "-").replace("‑", "-")
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)  # "₹1,000" must match the case's "1000"
    return re.sub(r"\s+", " ", re.sub(r"[*`₹]", "", text)).casefold()


def load_cases():
    return [json.loads(line) for line in CASES_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


def check(case, result):
    """Names of the assertions that failed (empty list = pass)."""
    failed = []
    answer = _norm(result["answer"])
    if result["termination"] != "COMPLETED":
        failed.append(f"terminated:{result['termination']}")
    if case["not_covered"]:
        if not NOT_COVERED.search(result["answer"] or ""):
            failed.append("says_not_covered")
    else:
        failed += [f"missing:{t}" for t in case["must_contain"] if _norm(t) not in answer]
        if case["must_contain_any"] and not any(_norm(t) in answer for t in case["must_contain_any"]):
            failed.append(f"missing_any:{case['must_contain_any']}")
        if not result["citations"] or not all("Revision 11" in c["version"] for c in result["citations"]):
            failed.append("cites_revision")
        if result["ungrounded"]:
            failed.append(f"ungrounded:{result['ungrounded']}")
    failed += [f"forbidden:{t}" for t in case["must_not_contain"] if _norm(t) in answer]
    if case["secrets"]:
        logs = Path(result["trace_file"]).read_text(encoding="utf-8")
        mcp_log = (HERE.parent / "Agentic Ai" / "output" / "mcp_trace.jsonl").read_text(encoding="utf-8")
        failed += [f"secret_in_logs:{s[:8]}" for s in case["secrets"] if s in logs or s in mcp_log or s in (result["answer"] or "")]
    return failed


def judge(question, answer, evidence):
    """Advisory faithfulness judge: is every claim in the answer stated in the retrieved excerpts?"""
    import llm_client

    excerpts = "\n---\n".join(f"[{e['chunk_id']}] {e['text']}" for e in evidence)[:6000] or "(no excerpts retrieved)"
    prompt = (
        "You check an HR assistant's answer against the handbook excerpts it retrieved.\n"
        'Reply with only JSON: {"verdict": "supported" or "unsupported", "reason": "<one sentence>"}.\n'
        "'supported' only if every factual claim (figures, times, names, rules) is stated in the excerpts. "
        "A plain statement that the handbook does not cover the topic is 'supported' when the excerpts do not cover it.\n\n"
        f"EXCERPTS:\n{excerpts}\n\nQUESTION: {question}\n\nANSWER: {answer}"
    )
    message, usage = llm_client.chat([{"role": "user", "content": prompt}], temperature=0)
    raw = (message.content or "").strip()
    try:
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        return data.get("verdict", "unparsed"), data.get("reason", ""), usage["total_tokens"]
    except (ValueError, json.JSONDecodeError):
        return "unparsed", raw[:200], usage["total_tokens"]


REVISIONS_FILE = HERE.parent / "Agentic Ai" / "handbook_revisions.json"


def with_register(evidence, tool_calls):
    """Judge evidence must include the revision register when the agent used it (seam 19: the judge
    never saw it, so it marked R01-R04 'unsupported: no excerpts retrieved' on correct answers)."""
    if any(c["tool"] == "get_handbook_revisions" for c in tool_calls):
        return evidence + [{"chunk_id": "handbook_revisions.json", "text": REVISIONS_FILE.read_text(encoding="utf-8")}]
    return evidence


def rejudge():
    """Re-score every stored answer with the current judge (no agent calls) and rewrite the label sheet."""
    rows = [json.loads(line) for line in RESULTS_FILE.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        trace = json.loads(Path(row["trace_file"]).read_text(encoding="utf-8"))
        evidence = with_register(trace["evidence"], trace["tool_calls"])
        row["judge"], row["judge_reason"], _ = judge(row["question"], row["answer"], evidence)
        print(row["id"], row["judge"], flush=True)
    RESULTS_FILE.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    verdicts = {r["id"]: r["judge"] for r in rows}
    labels = list(csv.DictReader(open(LABELS_FILE, encoding="utf-8")))
    for label in labels:
        label["judge_verdict"] = verdicts[label["case_id"]]
    with open(LABELS_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(labels[0]))
        w.writeheader()
        w.writerows(labels)
    agreement()


def _percentile(values, p):
    ordered = sorted(values)
    return ordered[max(0, -(-len(ordered) * p // 100) - 1)] if ordered else 0


def summarize(results):
    n = len(results)
    passed = sum(1 for r in results if r["passed"])
    lines = [f"# Integrated eval summary (n={n})", "", f"**Pass rate: {passed}/{n} ({passed / n:.0%})** (assertions only; judge is advisory)", "",
             "| Mode | n | passed | pass rate |", "|---|---:|---:|---:|"]
    for mode in sorted({r["mode"] for r in results}):
        rows = [r for r in results if r["mode"] == mode]
        ok = sum(1 for r in rows if r["passed"])
        lines.append(f"| {mode} | {len(rows)} | {ok} | {ok / len(rows):.0%} |")
    cost = [r["cost"] for r in results]
    total_s = [r["latency_s"] for r in results]
    model_s = [r["model_s"] for r in results]
    answered = [r for r in results if r["mode"] != "not_covered"]
    lines += ["", "| Metric | Value |", "|---|---:|",
              f"| Cost per question (mean / total) | ${statistics.mean(cost):.6f} / ${sum(cost):.4f} |",
              f"| Tokens per question (mean / max) | {statistics.mean(r['tokens'] for r in results):.0f} / {max(r['tokens'] for r in results)} |",
              f"| Latency incl. 429 waits p50 / p95 | {_percentile(total_s, 50):.1f}s / {_percentile(total_s, 95):.1f}s |",
              f"| Model-call time only p50 / p95 | {_percentile(model_s, 50):.1f}s / {_percentile(model_s, 95):.1f}s |",
              f"| Total 429 wait | {sum(r['rate_limit_wait_s'] for r in results):.0f}s |",
              f"| Answers with ungrounded figures | {sum(1 for r in answered if r['ungrounded'])}/{len(answered)} |",
              f"| Terminated early (budget) | {sum(1 for r in results if r['termination'] != 'COMPLETED')}/{n} |"]
    judged = [r for r in results if r.get("judge")]
    if judged:
        lines.append(f"| Judge 'supported' | {sum(1 for r in judged if r['judge'] == 'supported')}/{len(judged)} |")
    failures = [r for r in results if not r["passed"]]
    if failures:
        lines += ["", "## Failed cases", "", "| Case | Trace | Failed assertions |", "|---|---|---|"]
        lines += [f"| {r['id']} | {r['trace_id']} | {'; '.join(r['failed'])} |" for r in failures]
    return "\n".join(lines) + "\n"


def selftest():
    base = {"must_contain": [], "must_contain_any": [], "must_not_contain": [], "not_covered": False, "secrets": []}
    cite = [{"version": "Revision 11 (June 2025)"}]
    ok = {"answer": "Technical staff: unused leaves are **encashed**.", "termination": "COMPLETED", "citations": cite, "ungrounded": []}
    assert check({**base, "must_contain_any": ["encash"], "must_not_contain": ["nine"]}, ok) == []
    assert check({**base, "must_not_contain": ["encash"]}, ok) == ["forbidden:encash"]
    assert check({**base, "must_contain": ["1000"]}, ok) == ["missing:1000"]
    assert check(base, {**ok, "citations": []}) == ["cites_revision"]
    assert check(base, {**ok, "ungrounded": ["15"]}) == ["ungrounded:['15']"]
    assert check(base, {**ok, "termination": "MAX_TOKENS_EXCEEDED"}) == ["terminated:MAX_TOKENS_EXCEEDED"]
    refusal = {**ok, "answer": "That is not covered in the Employee Handbook.", "citations": []}
    assert check({**base, "not_covered": True}, refusal) == []
    assert check({**base, "not_covered": True}, ok) == ["says_not_covered"]
    assert _norm("2:00 pm **11:30** pm") == "2:00 pm 11:30 pm"
    assert _norm("**₹1,000** per day") == "1000 per day"  # seam 16: this false-failed G08 and G10
    results = [{"mode": "m", "passed": True, "cost": 0.1, "tokens": 10, "latency_s": 1, "model_s": 1, "rate_limit_wait_s": 0,
                "ungrounded": [], "termination": "COMPLETED", "id": "a", "trace_id": "t", "failed": []}]
    assert "1/1 (100%)" in summarize(results)


def run(judge_on=True, only=None):
    import capstone

    judge_fn = judge
    OUT.mkdir(exist_ok=True)
    cases = [c for c in load_cases() if not only or c["id"] in only]
    kept = {}
    if only and RESULTS_FILE.exists():
        kept = {r["id"]: r for r in map(json.loads, RESULTS_FILE.read_text(encoding="utf-8").splitlines()) if r["id"] not in only}
    results = dict(kept)
    for case in cases:
        result = capstone.ask(case["question"], group=case["group"], question_id=case["id"])
        failed = check(case, result)
        row = {"id": case["id"], "mode": case["mode"], "group": case["group"], "passed": not failed, "failed": failed,
               "trace_id": result["trace_id"], "trace_file": result["trace_file"], "termination": result["termination"],
               "cost": result["cost"], "tokens": result["tokens"], "latency_s": result["latency_s"],
               "model_s": result["model_s"], "tool_s": result["tool_s"], "rate_limit_wait_s": result["rate_limit_wait_s"],
               "ungrounded": result["ungrounded"], "answer": result["answer"], "question": case["question"],
               "evidence_ids": [e["chunk_id"] for e in result["evidence"]]}
        if judge_on:
            row["judge"], row["judge_reason"], _ = judge_fn(case["question"], result["answer"], with_register(result["evidence"], result["tool_calls"]))
        results[case["id"]] = row
        RESULTS_FILE.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in results.values()) + "\n", encoding="utf-8")
        print(f"{'PASS' if row['passed'] else 'FAIL'} {case['id']:<28} {row['tokens']:>6} tok  {row['latency_s']:>5.1f}s  {row['failed'] or ''}", flush=True)
        if result["rate_limit_wait_s"] > 60:  # daily quota, not the system: results from here on would be junk
            print(f"STOP after {case['id']}: {result['rate_limit_wait_s']:.0f}s of 429 wait. Retry later with --only <remaining ids>.")
            break
        time.sleep(max(0.0, (result["tokens"] + 1500) / 100 - result["latency_s"]))  # stay under 8,000 TPM

    ordered = [results[c["id"]] for c in load_cases() if c["id"] in results]
    SUMMARY_FILE.write_text(summarize(ordered), encoding="utf-8")
    if judge_on and not LABELS_FILE.exists():  # never overwrite hand labels
        with open(LABELS_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["case_id", "trace_id", "question", "answer", "evidence_chunks", "judge_verdict", "judge_reason", "claude_draft_label", "human_label", "note"])
            for r in ordered:
                w.writerow([r["id"], r["trace_id"], r["question"], r["answer"], " ".join(r["evidence_ids"]), r.get("judge", ""), r.get("judge_reason", ""), "", "", ""])
    print(SUMMARY_FILE.read_text(encoding="utf-8"))


def agreement():
    """Judge vs labels. Uses `human_label` where filled, otherwise `claude_draft_label` (printed as a draft,
    not hand labels). Rows with no label (invalid quota runs) are skipped."""
    rows = list(csv.DictReader(open(LABELS_FILE, encoding="utf-8")))
    hand = [r for r in rows if r["human_label"].strip()]
    using, key = ("HAND labels", "human_label") if hand else ("Claude-DRAFTED labels (not yet confirmed by a human)", "claude_draft_label")
    rows = [r for r in rows if r[key].strip()]
    if not rows:
        raise SystemExit("No labels yet: fill human_label in judge_labels.csv.")
    wrong = [r for r in rows if r[key].strip().lower() != r["judge_verdict"].strip().lower()]
    print(f"judge agreement with {using}: {len(rows) - len(wrong)}/{len(rows)} = {(len(rows) - len(wrong)) / len(rows):.0%} (target >= 85%)")
    for r in wrong:
        print("  disagree:", r["case_id"], "judge:", r["judge_verdict"], "label:", r[key], "|", r.get("note", ""))


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    if sys.argv[1:] == ["agreement"]:
        agreement()
    elif sys.argv[1:] == ["rejudge"]:
        rejudge()
    else:
        raise SystemExit("usage: python eval_integrated.py agreement   (run the suite with: python capstone.py eval)")
