import json
import re
import sys
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parent
SRC_DIR = TASK_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import chromadb

from create_embeddings import model as embedding_model
from ingest import CHROMA_PATH, COLLECTIONS
from questions import QUESTIONS

TOP_K = 5


def query_collection(collection, question_text):
    embedding = embedding_model.encode(question_text).tolist()
    results = collection.query(query_embeddings=[embedding], n_results=TOP_K)

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
            "page_id": metadata["page_id"],
            "sdk_version": metadata["sdk_version"],
            "anchor": metadata["anchor"],
            "document": document,
            "snippet": document[:160].replace("\n", " "),
        })
    return rows


def _normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def is_hit(rows, question, chunk_lookup):
    """A hit requires the retrieved chunk to belong to the correct page AND
    literally contain the fact the question depends on (its expected_fragment),
    not merely be from the right page. A chunk that only touches the right
    page without the fact itself (e.g. the intro paragraph) does not count."""
    fragment = _normalize(question["expected_fragment"])
    for row in rows:
        if row["page_id"] != question["correct_page_id"]:
            continue
        if row["sdk_version"] != question["correct_sdk_version"]:
            continue
        if fragment in _normalize(chunk_lookup[row["chunk_id"]]):
            return True
    return False


def run():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collections = {
        method: client.get_collection(name=name)
        for method, name in COLLECTIONS.items()
    }

    report = {method: {"hits": 0, "results": []} for method in collections}

    for question in QUESTIONS:
        for method, collection in collections.items():
            rows = query_collection(collection, question["question"])
            chunk_lookup = {row["chunk_id"]: row["document"] for row in rows}
            hit = is_hit(rows, question, chunk_lookup)
            report[method]["hits"] += int(hit)
            report[method]["results"].append({
                "id": question["id"],
                "question": question["question"],
                "correct_page_id": question["correct_page_id"],
                "correct_sdk_version": question["correct_sdk_version"],
                "hit_in_top5": hit,
                "top5": rows,
            })

    for method in report:
        print(f"{method}: {report[method]['hits']}/{len(QUESTIONS)}")

    output_path = TASK_DIR / "output" / "search_dump.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Full dump written to {output_path}")

    return report


if __name__ == "__main__":
    run()
