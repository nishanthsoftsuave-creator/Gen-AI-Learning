import json
import random
from pathlib import Path

SEED = 20260905
SAMPLE_SIZE = 20

BASE_DIR = Path(__file__).resolve().parent.parent
TRACE_DIR = BASE_DIR / "output" / "traces"
OUTPUT_FILE = BASE_DIR / "sdk_docs_task" / "output" / "current_selected_traces.json"

trace_files = sorted(TRACE_DIR.glob("*.json"))

if len(trace_files) < SAMPLE_SIZE:
    raise ValueError(
        f"Need at least {SAMPLE_SIZE} traces, but found {len(trace_files)}."
    )

rng = random.Random(SEED)

selected_files = rng.sample(trace_files, SAMPLE_SIZE)

selected_files = sorted(
    selected_files,
    key=lambda path: path.name,
)

selected_traces = []

for trace_file in selected_files:
    trace = json.loads(
        trace_file.read_text(encoding="utf-8")
    )

    selected_traces.append(
        {
            "trace_id": trace["trace_id"],
            "question": trace["question"],
            "file": str(trace_file.relative_to(BASE_DIR)),
        }
    )

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE.write_text(
    json.dumps(
        {
            "seed": SEED,
            "population_size": len(trace_files),
            "sample_size": SAMPLE_SIZE,
            "traces": selected_traces,
        },
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)

print(f"Population: {len(trace_files)}")
print(f"Sample size: {SAMPLE_SIZE}")
print(f"Seed: {SEED}")
print(f"Saved to: {OUTPUT_FILE}")

print("\nSelected traces:")

for item in selected_traces:
    print(
        f"{item['trace_id']} — {item['question']}"
    )