import json
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TASK_DIR = Path(__file__).resolve().parent
SRC_DIR = TASK_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import chromadb
from dotenv import load_dotenv
from groq import Groq

from create_embeddings import model as embedding_model
from ingest import CHROMA_PATH, COLLECTIONS
from questions import QUESTIONS, OUT_OF_CORPUS_QUESTIONS

load_dotenv(TASK_DIR.parent / ".env")

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

METHOD = "structure_aware"
TOP_K = 5

REFUSAL_TEXT = "NOT_IN_CORPUS: This is not documented in the provided SDK reference pages."

SYSTEM_PROMPT = f"""You are a documentation assistant for the Nimbus SDK. Answer ONLY using the numbered context chunks provided below. Each chunk is labeled with its chunk_id.

Rules (mandatory -- not suggestions):
1. Every factual claim in your answer must end with a citation in the exact form [chunk_id], where chunk_id is copied verbatim from a context label below (write it exactly as "[chunk_id]", not "[chunk_id=chunk_id]").
2. You may only cite a chunk_id that literally appears in the context below. Never invent a chunk_id.
3. A chunk about a related-but-different subject does NOT support the answer. A general client-side setting (e.g. the SDK's own rate limiter) is NOT evidence for a question about a specific, different thing (e.g. one HTTP endpoint's rate limit) even if both involve the same keyword. Only use a chunk if it names the exact subject of the question.
4. If the context does not fully and specifically support an answer to the question, you MUST reply with EXACTLY this text and nothing else, no exceptions, even if you believe you know the answer from general knowledge:
{REFUSAL_TEXT}
5. Do not use outside knowledge. Do not guess. Do not hedge with "likely" or "typically" -- either cite a chunk_id or refuse with the exact text above."""


def retrieve(collection, question_text, top_k=TOP_K):
    embedding = embedding_model.encode(question_text).tolist()
    results = collection.query(query_embeddings=[embedding], n_results=top_k)

    rows = []
    for chunk_id, document, metadata in zip(
        results["ids"][0], results["documents"][0], results["metadatas"][0]
    ):
        rows.append({"chunk_id": chunk_id, "document": document, "metadata": metadata})
    return rows


def build_context(rows):
    return "\n\n---\n\n".join(
        f"[chunk_id={row['chunk_id']}]\n{row['document']}" for row in rows
    )


def generate(question_text, rows):
    context = build_context(rows)
    user_prompt = f"Context:\n{context}\n\nQuestion: {question_text}\n\nAnswer:"

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def resolve_citations(answer_text, rows):
    cited = set(re.findall(r"[\[【](?:chunk_id=)?([a-zA-Z0-9_-]+)[\]】]", answer_text))
    resolved = []
    for chunk_id in cited:
        row = next((r for r in rows if r["chunk_id"] == chunk_id), None)
        resolved.append({
            "chunk_id": chunk_id,
            "resolves": row is not None,
            "source_file": row["metadata"]["source_file"] if row else None,
            "anchor": row["metadata"]["anchor"] if row else None,
        })
    return resolved


def run_answerable(client, target_ids=("Q3", "Q6", "Q7")):
    collection = client.get_collection(name=COLLECTIONS[METHOD])
    results = []
    for q in QUESTIONS:
        if q["id"] not in target_ids:
            continue
        rows = retrieve(collection, q["question"])
        answer = generate(q["question"], rows)
        citations = resolve_citations(answer, rows)
        results.append({
            "id": q["id"],
            "question": q["question"],
            "known_answer": q["known_answer"],
            "retrieved_chunk_ids": [r["chunk_id"] for r in rows],
            "answer": answer,
            "citations": citations,
        })
    return results


def run_refusals(client):
    collection = client.get_collection(name=COLLECTIONS[METHOD])
    results = []
    for q in OUT_OF_CORPUS_QUESTIONS:
        rows = retrieve(collection, q["question"])
        answer = generate(q["question"], rows)
        results.append({
            "id": q["id"],
            "question": q["question"],
            "why_unanswerable": q["why_unanswerable"],
            "retrieved_chunk_ids": [r["chunk_id"] for r in rows],
            "answer": answer,
            "correctly_refused": answer.strip() == REFUSAL_TEXT,
        })
    return results


def run_bonus(client):
    """Structure-aware wins retrieval precision but loses generation
    completeness because the tight Parameters chunk carries no code sample."""
    question = (
        "What is the default chunk_size_mb for BatchUploader.upload(), "
        "and how is it passed in the example code?"
    )
    out = {"question": question, "by_strategy": {}}
    for method in ("recursive", "structure_aware"):
        collection = client.get_collection(name=COLLECTIONS[method])
        rows = retrieve(collection, question, top_k=3)
        answer = generate(question, rows)
        out["by_strategy"][method] = {
            "retrieved": [
                {"chunk_id": r["chunk_id"], "has_code_fence": "```" in r["document"]}
                for r in rows
            ],
            "answer": answer,
        }
    return out


if __name__ == "__main__":
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    answerable = run_answerable(client)
    refusals = run_refusals(client)
    bonus = run_bonus(client)

    for r in answerable:
        print(f"\n=== {r['id']} ===")
        print(r["question"])
        print("ANSWER:", r["answer"])
        print("CITATIONS:", r["citations"])

    for r in refusals:
        print(f"\n=== {r['id']} (refusal) ===")
        print(r["question"])
        print("ANSWER:", r["answer"])
        print("CORRECTLY REFUSED:", r["correctly_refused"])

    print("\n=== BONUS ===")
    print(json.dumps(bonus, indent=2))

    out_path = TASK_DIR / "output" / "generation_dump.json"
    out_path.write_text(
        json.dumps({"answerable": answerable, "refusals": refusals, "bonus": bonus}, indent=2),
        encoding="utf-8",
    )
    print(f"\nWritten to {out_path}")
