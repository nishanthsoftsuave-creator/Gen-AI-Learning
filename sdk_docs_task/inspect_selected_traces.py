import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SELECTED_FILE = (
    BASE_DIR
    / "sdk_docs_task"
    / "output"
    / "current_selected_traces.json"
)

selected = json.loads(
    SELECTED_FILE.read_text(encoding="utf-8")
)

for item in selected["traces"]:
    trace_file = BASE_DIR / item["file"]

    trace = json.loads(
        trace_file.read_text(encoding="utf-8")
    )

    print("\n" + "=" * 80)
    print(f"TRACE ID: {trace['trace_id']}")
    print(f"QUESTION: {trace['question']}")
    print(f"ANSWER: {trace['raw_output']}")

    print("\nRETRIEVED CHUNKS:")

    for chunk in trace["retrieval"]["chunks"]:
        print(
            f"\n  Rank: {chunk['rank']}"
            f"\n  Chunk ID: {chunk['chunk_id']}"
            f"\n  Score: {chunk['score']}"
            f"\n  Text: {chunk['text'][:500].replace(chr(10), ' ')}"
        )