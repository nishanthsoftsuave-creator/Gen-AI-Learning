"""
Step 2: Deterministic random sampling of 20 traces from available trace data.
Seed: 20260830 (today's date)
"""
import json
import random
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parent
SEED = 20260830

# Load all available trace data
generation_dump = json.loads((TASK_DIR / "output" / "generation_dump.json").read_text(encoding="utf-8"))
search_dump = json.loads((TASK_DIR / "output" / "search_dump.json").read_text(encoding="utf-8"))
week4_baseline = json.loads((TASK_DIR / "output" / "week4_baseline.json").read_text(encoding="utf-8"))
week4_after = json.loads((TASK_DIR / "output" / "week4_after.json").read_text(encoding="utf-8"))

# Build population of all traces
# Each trace is a unique (source, question_id) combination with all available data
traces = []

# 1. generation_dump answerable traces (3)
for item in generation_dump["answerable"]:
    traces.append({
        "trace_id": f"gen_{item['id']}",
        "source": "generation_dump",
        "question_id": item["id"],
        "question": item["question"],
        "known_answer": item.get("known_answer", ""),
        "retrieved_chunk_ids": item.get("retrieved_chunk_ids", []),
        "answer": item.get("answer", ""),
        "hit": True,  # answerable = correct retrieval
        "has_generation": True,
    })

# 2. generation_dump refusal traces (3)
for item in generation_dump["refusals"]:
    traces.append({
        "trace_id": f"gen_{item['id']}",
        "source": "generation_dump",
        "question_id": item["id"],
        "question": item["question"],
        "known_answer": item.get("why_unanswerable", ""),
        "retrieved_chunk_ids": item.get("retrieved_chunk_ids", []),
        "answer": item.get("answer", ""),
        "hit": False,
        "has_generation": True,
    })

# 3. search_dump recursive traces (8)
for item in search_dump["recursive"]["results"]:
    traces.append({
        "trace_id": f"search_rec_{item['id']}",
        "source": "search_dump_recursive",
        "question_id": item["id"],
        "question": item["question"],
        "known_answer": "",
        "retrieved_chunk_ids": [r["chunk_id"] for r in item["top5"]],
        "retrieval_distances": [r["distance"] for r in item["top5"]],
        "hit_in_top5": item.get("hit_in_top5", False),
        "answer": "",
        "has_generation": False,
    })

# 4. search_dump structure_aware traces (8)
for item in search_dump["structure_aware"]["results"]:
    traces.append({
        "trace_id": f"search_sa_{item['id']}",
        "source": "search_dump_structure_aware",
        "question_id": item["id"],
        "question": item["question"],
        "known_answer": "",
        "retrieved_chunk_ids": [r["chunk_id"] for r in item["top5"]],
        "retrieval_distances": [r["distance"] for r in item["top5"]],
        "hit_in_top5": item.get("hit_in_top5", False),
        "answer": "",
        "has_generation": False,
    })

# 5. week4_baseline traces (12)
for i, item in enumerate(week4_baseline["results"]):
    traces.append({
        "trace_id": f"w4b_{i+1:02d}",
        "source": "week4_baseline",
        "question_id": f"W4B_{i+1}",
        "question": item["question"],
        "known_answer": "",
        "expected_chunk_id": item["expected_chunk_id"],
        "retrieved_chunk_ids": item["retrieved_ids"],
        "hit": item["hit"],
        "latency_ms": item["latency_ms"],
        "has_generation": False,
    })

# 6. week4_after traces (12)
for i, item in enumerate(week4_after["results"]):
    traces.append({
        "trace_id": f"w4a_{i+1:02d}",
        "source": "week4_after",
        "question_id": f"W4A_{i+1}",
        "question": item["question"],
        "known_answer": "",
        "expected_chunk_id": item["expected_chunk_id"],
        "retrieved_chunk_ids": item["retrieved_ids"],
        "hit": item["hit"],
        "latency_ms": item["latency_ms"],
        "has_generation": False,
    })

print(f"Total population: {len(traces)} traces")
print(f"Sources:")
from collections import Counter
source_counts = Counter(t["source"] for t in traces)
for source, count in source_counts.items():
    print(f"  {source}: {count}")

# Deterministic random sampling
rng = random.Random(SEED)
selected_indices = sorted(rng.sample(range(len(traces)), 20))
selected = [traces[i] for i in selected_indices]

print(f"\nRandom seed: {SEED}")
print(f"\nSelected 20 trace IDs:")
for i, t in enumerate(selected, 1):
    print(f"  {i:2d}. {t['trace_id']} ({t['source']}) — Q: {t['question'][:70]}...")

# Save selected traces for later use
output = {
    "seed": SEED,
    "population_size": len(traces),
    "sample_size": 20,
    "selected_traces": selected,
}
(TASK_DIR / "output" / "selected_traces.json").write_text(
    json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
)
print(f"\nSelected traces saved to output/selected_traces.json")
