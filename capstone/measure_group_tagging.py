"""Offline before/after for the chunk-boundary group bleed (no LLM, no API quota).

Runs the same group-scoped queries through the real search_handbook (hybrid retrieve + group filter)
under three index states and counts, per caller group:
  miss : the caller's own rule is absent from the top-3 (technical callers, needle = outstation 1000 INR)
  bleed: the OTHER group's figure reaches the caller's retrieved text (non-technical callers see 500/1000 INR)

  naive          group tag from each chunk's own text           (the state that failed G06/G07/G09)
  overlap        + inherit the group in effect at the overlap   (fixes the miss, keeps the bleed)
  overlap+trim   + drop the other group's leading span          (final)

Leaves the index in the final (overlap+trim) state.
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
for path in (BASE / "src", BASE / "Agentic Ai", HERE):
    sys.path.insert(0, str(path))
os.environ.pop("HR_VIA_MCP", None)

import tag_index  # noqa: E402
import tools  # noqa: E402

TECH_QUERIES = [  # the answer ("1000 INR per day") exists only in chunk_57
    "How much am I paid if a recruitment drive needs outstation travel on a non working day?",
    "recruitment drive outstation travel compensation per day",
    "what is the pay for travelling outstation for hiring drive on a weekend",
    "offline recruitment drive non working day outstation INR",
    "Do I get extra money when the recruitment drive is in another city?",
    "recruitment drive that requires travel outstation, how much per day",
    "technical team compensation outstation recruitment drive",
    "monetary compensation for recruitment drive travel outstation non working days",
    "I am asked to travel outstation for company hiring on my day off. What do I get?",
    "outstation recruitment drive 1000 INR per day eligibility",
]
NEEDLE = "1000 INR per day"
NONTECH_QUERIES = [  # the answer is "equivalent to one day compensation"; any INR figure is the other team's
    "What compensation do I get for working on a company holiday?",
    "I worked 8 hours on a company holiday, what do I get?",
    "non technical team holiday work compensation",
    "working on holidays minimum 8 hours compensation",
    "Is there monetary compensation for holiday work?",
    "how am I compensated if I work on a company holiday for 8 hours",
    "non-technical employee working on public holiday",
    "compensation for working on non working day recruitment drive",
]
OTHER_TEAM_FIGURES = ("500 INR", "1000 INR", "outstation")


def retrieved_text(query, group):
    return " ".join(r["text"] for r in tools.search_handbook(query, top_k=3, employee_group=group)["results"])


def measure():
    miss = sum(NEEDLE not in " ".join(retrieved_text(q, "technical").split()) for q in TECH_QUERIES)
    bleed = sum(any(f in retrieved_text(q, "non_technical") for f in OTHER_TEAM_FIGURES) for q in NONTECH_QUERIES)
    # Residual in the other direction (accepted): a technical caller sees the non-technical rule's opening line.
    tech_sees_other = sum("equivalent to one day" in retrieved_text(q, "technical") for q in TECH_QUERIES)
    return {"technical_miss": miss, "technical_n": len(TECH_QUERIES), "nontech_bleed": bleed,
            "nontech_n": len(NONTECH_QUERIES), "tech_sees_nontech_rule": tech_sees_other}


def main():
    real_trim = tools._trim_foreign_lead
    states = []
    for label, mode, trim in (("naive", "naive", True), ("overlap", "overlap", False), ("overlap+trim", "overlap", True)):
        counts = tag_index.tag(mode)
        tools._trim_foreign_lead = real_trim if trim else (lambda text, meta, group: text)
        states.append({"state": label, "tags": counts, **measure()})
    tools._trim_foreign_lead = real_trim
    out = HERE / "output" / "group_tagging_measure.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(states, indent=2), encoding="utf-8")
    print(f"{'state':<14}{'tech miss':>12}{'non-tech bleed':>17}{'tech sees non-tech rule':>26}")
    for s in states:
        print(f"{s['state']:<14}{s['technical_miss']:>6}/{s['technical_n']:<5}{s['nontech_bleed']:>10}/{s['nontech_n']:<6}"
              f"{s['tech_sees_nontech_rule']:>18}/{s['technical_n']}")


if __name__ == "__main__":
    main()
