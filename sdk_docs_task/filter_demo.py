import json
import sys
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parent
SRC_DIR = TASK_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import chromadb

from create_embeddings import model as embedding_model
from ingest import CHROMA_PATH, COLLECTIONS

QUERY = "What is the default value and type of retry_backoff_ms on Client.send()?"
METHOD = "recursive"
TOP_K = 5


def run_query(collection, where=None):
    embedding = embedding_model.encode(QUERY).tolist()
    kwargs = {"query_embeddings": [embedding], "n_results": TOP_K}
    if where:
        kwargs["where"] = where
    results = collection.query(**kwargs)

    rows = []
    for chunk_id, document, metadata, distance in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        rows.append({
            "chunk_id": chunk_id,
            "distance": distance,
            "source_file": metadata["source_file"],
            "sdk_version": metadata["sdk_version"],
            "anchor": metadata["anchor"],
            "snippet": document[:180].replace("\n", " "),
        })
    return rows


def run():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(name=COLLECTIONS[METHOD])

    unfiltered = run_query(collection)
    filtered = run_query(collection, where={"sdk_version": "v3"})

    report = {
        "query": QUERY,
        "collection": COLLECTIONS[METHOD],
        "unfiltered_top1": unfiltered[0],
        "filtered_top1": filtered[0],
        "top1_changed": unfiltered[0]["chunk_id"] != filtered[0]["chunk_id"],
        "unfiltered": unfiltered,
        "filtered": filtered,
    }

    print(json.dumps(report, indent=2))

    output_path = TASK_DIR / "output" / "filter_demo.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWritten to {output_path}")

    return report


if __name__ == "__main__":
    run()
