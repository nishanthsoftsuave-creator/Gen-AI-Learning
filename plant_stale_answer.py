"""Squadmate tool: plant ONE stale-policy answer in the traces, blind to the finder.

  python plant_stale_answer.py --manifest D:/somewhere/the/finder/cannot/see.json

Prints only the trace count, never what was planted. Each variant contradicts the
handbook (revision register in Agentic Ai/handbook_revisions.json; leave rules in
handbook section 9). Spans and context ids are copied from a real leave trace.
"""
import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRACES = HERE / "output" / "traces"
BASE_TRACE = "tr_91795918c2d0"  # real leave trace: spans and context ids reused

VARIANTS = [
    ("Can non-technical employees carry forward unused leave?", "leave",
     "Yes. Non-technical employees can carry forward up to **15 unused leaves** to the next year.",
     "non-technical carry-forward is max nine"),
    ("What happens to unused leave for technical team members?", "leave",
     "Unused leave for technical team members **lapses at the end of the year** with no payout.",
     "technical unused leave is encashed at the day's salary"),
    ("When were Revisions 9 and 10 of the Employee Handbook issued?", "revision-history",
     "Revisions 9 and 10 were both issued in **2024**.",
     "both are dated May 2023"),
    ("What is the latest revision of the Employee Handbook?", "revision-history",
     "The latest is **Revision 10**, dated May 2023.",
     "latest is Revision 11, June 2025"),
]


def plant(traces_dir=TRACES, now=None):
    now = now or datetime.now(timezone.utc)
    base = json.loads((traces_dir / f"{BASE_TRACE}.json").read_text(encoding="utf-8"))
    users = sorted({
        t.get("user_ref")
        for t in (json.loads(f.read_text(encoding="utf-8")) for f in traces_dir.glob("tr_*.json"))
        if t.get("user_ref")
    }) or ["u_unknown"]
    question, category, answer, truth = random.choice(VARIANTS)
    trace_id = f"tr_{random.randbytes(6).hex()}"
    when = now - timedelta(days=random.randint(2, 6), minutes=random.randint(0, 1439))
    base.update(
        trace_id=trace_id, timestamp=when.isoformat(), user_ref=random.choice(users),
        question=question, category=category, raw_output=answer, prompt_version="rag_v1",
    )
    (traces_dir / f"{trace_id}.json").write_text(json.dumps(base, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"trace_id": trace_id, "timestamp": base["timestamp"], "user_ref": base["user_ref"],
            "stale_claim": answer, "truth": truth}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True, help="where to save the answer key (keep it from the finder)")
    args = p.parse_args()
    Path(args.manifest).write_text(json.dumps(plant(), indent=2), encoding="utf-8")
    print(f"planted; {len(list(TRACES.glob('tr_*.json')))} traces now. Start the stopwatch when you give the vague complaint.")
