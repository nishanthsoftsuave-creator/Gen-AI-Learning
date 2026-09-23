import json
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parent
data = json.loads((TASK_DIR / "output" / "search_dump.json").read_text(encoding="utf-8"))

lines = ["# Search-only dump -- all 8 questions x 2 chunking strategies (top 5, no metadata filter)\n"]

for method in ["recursive", "structure_aware"]:
    lines.append(f"\n## Strategy: {method}\n")
    for r in data[method]["results"]:
        lines.append(f"### {r['id']} -- hit_in_top5={r['hit_in_top5']}")
        lines.append(f"Question: {r['question']}")
        lines.append(f"Correct: {r['correct_sdk_version']}/{r['correct_page_id']}\n")
        for i, row in enumerate(r["top5"], start=1):
            lines.append(
                f"{i}. `{row['chunk_id']}` dist={row['distance']:.4f} "
                f"({row['source_file']}, anchor={row['anchor']})"
            )
            lines.append(f"   > {row['snippet']}")
        lines.append("")

output_path = TASK_DIR / "output" / "search_dump.md"
output_path.write_text("\n".join(lines), encoding="utf-8")
print(f"Written to {output_path}")
