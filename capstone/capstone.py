"""Integrated HR Handbook answer engine: the one entry point for the capstone.

  python capstone.py setup                          ingest the handbook PDF and tag chunks by employee group
  python capstone.py ask "question" [--group technical|non_technical]
  python capstone.py eval                           the full integrated eval suite (see eval_integrated.py)
  python capstone.py selftest                       fast offline checks (no API calls)
  python capstone.py serve-mcp                      serve the handbook tools over MCP (stdio) for any client

Flow for `ask`: redact the question -> resolve the employee group BEFORE retrieval -> agent loop
whose handbook tools run over MCP with the group forced by code -> revision guard + number-grounding
check -> citations that name the handbook revision and PDF page. One trace id covers every hop.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
AGENTIC = BASE / "Agentic Ai"
for path in (BASE / "src", AGENTIC, HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from redact import redact  # noqa: E402

PROMPT_VERSION = "cap_v1"
REVISIONS_FILE = AGENTIC / "handbook_revisions.json"
AUDIT_FILE = AGENTIC / "output" / "mcp_audit.jsonl"
HANDBOOK_PDF_GLOB = "SS Employee Handbook*.pdf"

INSTRUCTIONS = """Rules for this answer:
- State a figure (days, amounts, times, limits, emails) only if it appears in a tool result. Never use general HR knowledge.
- If the Employee Handbook does not contain the answer, say plainly "That is not covered in the Employee Handbook." and stop. Do not guess.
- If the rule differs between the Technical and Non-Technical team and the other team's rule appeared in your tool results, add one sentence stating it."""
GROUP_KNOWN = (
    "The employee is on the {label} team. Answer only for the {label} team and do not describe "
    "the other team's rules."
)
FALLBACK = "I couldn't complete that lookup. Please contact HR at teamhr@softsuave.com."
GROUP_UNKNOWN = (
    "The employee's team is not known. If the rule differs between the Technical and Non-Technical "
    "team, give both rules and say which team each applies to."
)

_NON_TECH = re.compile(r"non[\s\-]?technical", re.I)
_TECH = re.compile(r"(?<![a-z\-])technical", re.I)
_NUMBER = re.compile(r"\d[\d,]*(?:[.:]\d+)?")
_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")


def resolve_group(question, explicit=None):
    """Return (group, how). Done before retrieval; None means unresolved."""
    if explicit:
        return explicit, "argument"
    non_tech, tech = bool(_NON_TECH.search(question)), bool(_TECH.search(_NON_TECH.sub("", question)))
    if non_tech != tech:
        return ("non_technical" if non_tech else "technical"), "inferred from question"
    return None, "unresolved"


def _strip_commas(text):
    return re.sub(r"(?<=\d),(?=\d{3})", "", text).replace(" ", " ").replace(" ", " ")


def find_ungrounded(answer, haystack):
    """Figures and emails in `answer` that appear nowhere in `haystack` (deterministic check).

    shortcut: digit tokens only, words like "nine" are not checked, and single digits are skipped
    (list markers); upgrade to a number-word normaliser if suite cases start hiding there.
    """
    hay = _strip_commas(haystack).lower()
    missing = []
    # The model often names its sources ("chunk_46", "p. 22"); those numbers are references, not claims.
    answer = re.sub(r"chunks?[_ ]\d+(?:\s*(?:,|and|&)\s*\d+)*|\bp(?:age|p?\.)\s*\d+", " ", answer, flags=re.I)
    for token in _NUMBER.findall(_strip_commas(answer)):
        token = token.rstrip(".:")
        if len(token) > 1 and not re.search(rf"(?<![\d.]){re.escape(token)}(?!\d)", hay):
            missing.append(token)
    missing += [e for e in _EMAIL.findall(answer) if e.lower() not in hay]
    return sorted(set(missing))


def build_citations(evidence, revisions, used_register):
    label = f"Revision {revisions['latest_revision']['revision']} ({revisions['latest_revision']['date']})"
    pdf = next((BASE / "documents").glob(HANDBOOK_PDF_GLOB), None)
    seen, out = set(), []
    for chunk in evidence:
        if chunk["chunk_id"] in seen:
            continue
        seen.add(chunk["chunk_id"])
        page = chunk.get("page") or 0
        link = f"{pdf.as_uri()}#page={page}" if pdf and page else ""
        out.append({"doc": "Employee Handbook", "version": label, "page": page,
                    "chunk_id": chunk["chunk_id"], "link": link})
    if used_register:
        out.append({"doc": "Employee Handbook revision register", "version": label,
                    "page": 0, "chunk_id": "handbook_revisions.json", "link": ""})
    return out


def format_citations(citations):
    return "\n".join(
        f"[{c['doc']} · {c['version']}" + (f" · PDF p.{c['page']}" if c["page"] else "") + f" · {c['chunk_id']}]"
        + (f" {c['link']}" if c["link"] else "")
        for c in citations
    )


def _boot():
    """Point the host at a handbook-only MCP config and import the agent stack (once)."""
    if "tools" in sys.modules:
        return
    config = {"mcpServers": {"hr-handbook": {
        "name": "HR Handbook MCP server", "command": sys.executable,
        "args": [str(AGENTIC / "mcp_handbook_server.py")], "cwd": str(AGENTIC)}}}
    config_path = HERE / "output" / "mcp_config.json"
    config_path.parent.mkdir(exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    os.environ["HR_MCP_CONFIG"] = str(config_path)
    os.environ["HR_VIA_MCP"] = "1"
    import tools  # noqa: F401  (discovers the MCP tools at import)


def _audit_spans(trace_id):
    if not AUDIT_FILE.exists():
        return []
    rows = (json.loads(line) for line in AUDIT_FILE.read_text(encoding="utf-8").splitlines() if line.strip())
    return [r for r in rows if r.get("trace_id") == trace_id]


def ask(question, group=None, question_id="adhoc"):
    _boot()
    import agent
    import llm_client
    import mcp_host
    import tools
    from agent_tracing import TRACE_DIR
    from tracing import create_trace_id

    started = time.monotonic()
    trace_id = create_trace_id()
    clean = redact(question)  # secrets never reach the model or the logs
    group, group_source = resolve_group(clean, group)
    revisions = json.loads(REVISIONS_FILE.read_text(encoding="utf-8"))

    tools.CALLER_GROUP.set(group)
    evidence = []
    tools.EVIDENCE.set(evidence)
    mcp_host.TRACE_ID.set(trace_id)
    before = dict(llm_client.STATS)
    label = {"technical": "Technical", "non_technical": "Non-Technical"}.get(group)
    instruction = INSTRUCTIONS + "\n" + (GROUP_KNOWN.format(label=label) if group else GROUP_UNKNOWN)

    try:
        result = agent.run_agent(clean, question_id=question_id, role_instruction=instruction, trace_id=trace_id)
    except Exception as error:  # e.g. Groq 400 tool_use_failed when the model invents a tool argument
        from agent_tracing import save_run_trace
        reason = f"ERROR:{type(error).__name__}"
        _, error_trace = save_run_trace("agent", question_id, clean, 0, [], [], 0, 0, 0, 0.0,
                                        time.monotonic() - started, reason, f"{reason}: {error}"[:300],
                                        llm_client.GROQ_MODEL, trace_id=trace_id)
        result = {"answer": None, "tool_calls": [], "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
                  "cost": 0.0, "termination_reason": reason, "trace_file": str(error_trace)}
    answer = result["answer"] or ""
    if result["termination_reason"] != "COMPLETED":
        answer = FALLBACK  # never show the user the internal "[No final answer...]" text

    if re.search(r"revision|revised", clean, re.I):
        from revision_guard import enforce_revision_authority
        answer = enforce_revision_authority(clean, answer, REVISIONS_FILE)

    used_register = any(c["tool"] == "get_handbook_revisions" for c in result["tool_calls"])
    haystack = " ".join([clean, json.dumps(revisions)] + [c["text"] for c in evidence])
    ungrounded = find_ungrounded(answer, haystack)
    if ungrounded:
        answer += f"\n\nNot verified against the retrieved handbook text: {', '.join(ungrounded)}."
    citations = build_citations(evidence, revisions, used_register)

    audit = _audit_spans(trace_id)
    tool_seconds = sum(r["latency_ms"] for r in audit) / 1000
    model_seconds = llm_client.STATS["model_call_seconds"] - before["model_call_seconds"]
    wait_seconds = llm_client.STATS["rate_limit_wait_seconds"] - before["rate_limit_wait_seconds"]
    total_seconds = time.monotonic() - started
    spans = [
        {"span": "model_calls", "n": len(result["tool_calls"]) + 1, "latency_s": round(model_seconds, 3),
         "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"], "cost_usd": result["cost"]},
        {"span": "mcp_tool_calls", "n": len(audit), "latency_s": round(tool_seconds, 3),
         "calls": [{"tool": r["tool"], "latency_ms": r["latency_ms"], "group": r["employee_group"]} for r in audit],
         "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        {"span": "rate_limit_wait", "latency_s": round(wait_seconds, 3)},
        {"span": "total", "latency_s": round(total_seconds, 3)},
    ]

    trace_file = Path(result["trace_file"])
    trace = json.loads(trace_file.read_text(encoding="utf-8"))
    trace.update({
        "prompt_version": PROMPT_VERSION, "employee_group": group, "group_source": group_source,
        "question_redacted": clean != question,
        "evidence": [{"tool": c["tool"], "chunk_id": c["chunk_id"], "page": c.get("page"), "text": c["text"]} for c in evidence],
        "citations": citations, "ungrounded_figures": ungrounded, "spans": spans,
        "final_answer_after_guards": answer,
    })
    trace_file.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "trace_id": trace_id, "question_id": question_id, "question": question, "answer": answer,
        "group": group, "group_source": group_source, "citations": citations, "ungrounded": ungrounded,
        "tool_calls": result["tool_calls"], "evidence": evidence, "termination": result["termination_reason"],
        "cost": result["cost"], "tokens": result["total_tokens"], "latency_s": total_seconds,
        "model_s": model_seconds, "tool_s": tool_seconds, "rate_limit_wait_s": wait_seconds,
        "trace_file": str(trace_file),
    }


def setup():
    from vector_store import store_embeddings
    import tag_index

    pdf = next((BASE / "documents").glob(HANDBOOK_PDF_GLOB))
    print(store_embeddings(str(pdf), reset=True, verbose=False))
    print("group tags:", tag_index.tag("overlap", pdf=pdf))


def selftest():
    assert resolve_group("how many leaves?", None) == (None, "unresolved")
    assert resolve_group("I am in the technical team", None)[0] == "technical"
    assert resolve_group("non-technical carry forward?", None)[0] == "non_technical"
    assert resolve_group("technical versus non-technical pay", None)[0] is None  # both named: do not guess
    assert resolve_group("anything", "technical") == ("technical", "argument")
    hay = "paid 1,000 INR per day, 500 INR; mail teamhr@softsuave.com; 2:00 pm to 11:30 pm; 9.30 hours"
    assert find_ungrounded("You get 1000 INR and 500 INR, 2:00 pm, 9.30 hours: teamhr@softsuave.com", hay) == []
    assert find_ungrounded("You get 1500 INR; email hr@evil.com", hay) == ["1500", "hr@evil.com"]
    assert find_ungrounded("1. first 2. second", hay) == []  # list markers are not figures
    assert find_ungrounded("stated in chunk_46 on p. 22 and page 23", hay) == []  # source references, not claims
    assert find_ungrounded("see chunks 17 and 19", hay) == []  # plural form, seen on L05
    assert find_ungrounded("see the passage in chunk 56", hay) == []  # seam 18: the model writes "chunk 56" too
    from revision_guard import enforce_revision_authority
    rev9_10 = "Revisions 9 and 10 were both issued in May 2023."
    assert enforce_revision_authority("When were Revisions 9 and 10 issued?", rev9_10, REVISIONS_FILE) == rev9_10  # seam 17
    cites = build_citations([{"chunk_id": "chunk_47", "page": 22, "tool": "search_handbook", "text": ""}] * 2,
                            {"latest_revision": {"revision": 11, "date": "June 2025"}}, False)
    assert len(cites) == 1 and "Revision 11 (June 2025)" in format_citations(cites) and "p.22" in format_citations(cites)
    import eval_integrated
    eval_integrated.selftest()
    print("capstone selftest OK")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup")
    sub.add_parser("selftest")
    sub.add_parser("serve-mcp")
    ask_parser = sub.add_parser("ask")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--group", choices=["technical", "non_technical"])
    eval_parser = sub.add_parser("eval")
    eval_parser.add_argument("--no-judge", action="store_true", help="assertions only, skip the LLM judge")
    eval_parser.add_argument("--only", help="comma-separated case ids")
    args = parser.parse_args()

    if args.command == "setup":
        setup()
    elif args.command == "selftest":
        selftest()
    elif args.command == "serve-mcp":
        import runpy
        runpy.run_path(str(AGENTIC / "mcp_handbook_server.py"), run_name="__main__")
    elif args.command == "ask":
        sys.stdout.reconfigure(encoding="utf-8")
        r = ask(args.question, args.group)
        print(r["answer"])
        print("\nCitations:\n" + (format_citations(r["citations"]) or "(none: no handbook text was retrieved)"))
        print(f"\ngroup={r['group']} ({r['group_source']})  trace={r['trace_id']}  termination={r['termination']}")
        print(f"cost=${r['cost']:.6f}  tokens={r['tokens']}  latency={r['latency_s']:.1f}s "
              f"(model {r['model_s']:.1f}s, tools {r['tool_s']:.1f}s, 429 wait {r['rate_limit_wait_s']:.1f}s)")
        if r["ungrounded"]:
            print("UNVERIFIED FIGURES:", r["ungrounded"])
    elif args.command == "eval":
        selftest()
        import eval_integrated
        eval_integrated.run(judge_on=not args.no_judge, only=args.only.split(",") if args.only else None)


if __name__ == "__main__":
    main()
