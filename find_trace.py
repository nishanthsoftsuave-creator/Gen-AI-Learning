"""Search saved traces by slice. Each flag is one slice; combine to narrow.

  python find_trace.py --since 2026-10-17 --text "carry forward"
  python find_trace.py --user u_ab12 --category leave --prompt-version rag_v1
  python find_trace.py --top-cost 5
"""
import argparse
import json
from pathlib import Path

TRACE_DIR = Path(__file__).resolve().parent / "output" / "traces"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--since", help="UTC date/time prefix, e.g. 2026-10-17 (>=)")
    p.add_argument("--until", help="UTC date/time prefix (<=)")
    p.add_argument("--user")
    p.add_argument("--category")
    p.add_argument("--prompt-version")
    p.add_argument("--text", help="case-insensitive match in the question OR the answer")
    p.add_argument("--top-cost", type=int, help="show the N most expensive traces")
    args = p.parse_args()

    traces = [json.loads(f.read_text(encoding="utf-8")) for f in TRACE_DIR.glob("tr_*.json")]
    hits = [
        t for t in traces
        if (not args.since or t.get("timestamp", "") >= args.since)
        and (not args.until or t.get("timestamp", "") <= args.until + "~")
        and (not args.user or t.get("user_ref") == args.user)
        and (not args.category or t.get("category") == args.category)
        and (not args.prompt_version or t.get("prompt_version") == args.prompt_version)
        and (not args.text or args.text.lower() in (t.get("question", "") + " " + t.get("raw_output", "")).lower())
    ]
    if args.top_cost:
        hits = sorted(hits, key=lambda t: t.get("total_cost_usd") or 0, reverse=True)[: args.top_cost]
    else:
        hits.sort(key=lambda t: t.get("timestamp", ""))

    for t in hits:
        print(
            f"{t['trace_id']}  {t.get('timestamp', '')[:19]}  {t.get('prompt_version')}  "
            f"user={t.get('user_ref')}  cat={t.get('category')}  cost={t.get('total_cost_usd')}\n"
            f"    Q: {t.get('question', '')[:100]}\n"
            f"    A: {t.get('raw_output', '')[:140]!r}"
        )
    print(f"\n{len(hits)} of {len(traces)} traces matched")


if __name__ == "__main__":
    main()
