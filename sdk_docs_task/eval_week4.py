"""
Week 4 Practical — Task Set E: Evaluation Script
=================================================
Runs baseline (dense-only) and after (dense + BM25 + RRF) experiments
against the SDK docs structure_aware collection.
"""

import json
import re
import statistics
import sys
import time
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parent
SRC_DIR = TASK_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import chromadb
import numpy as np
from collections import defaultdict

from create_embeddings import model as embedding_model

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CHROMA_PATH = str(TASK_DIR / "chroma_db")
COLLECTION_NAME = "sdk_docs_structure_aware"
TOP_K_BASELINE = 3  # For hit@3 measurement
TOP_K_CANDIDATES = 25  # For RRF candidate pool
RRF_K = 60  # Reciprocal Rank Fusion constant

GOLDEN_SET_PATH = TASK_DIR / "golden_set.jsonl"


# ---------------------------------------------------------------------------
# Load golden set
# ---------------------------------------------------------------------------
def load_golden_set():
    questions = []
    with open(GOLDEN_SET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


# ---------------------------------------------------------------------------
# Dense retrieval
# ---------------------------------------------------------------------------
def dense_retrieve(collection, question_text, top_k):
    embedding = embedding_model.encode(question_text).tolist()
    results = collection.query(
        query_embeddings=[embedding], n_results=min(top_k, collection.count())
    )
    rows = []
    for chunk_id, document, metadata, distance in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        rows.append({
            "chunk_id": chunk_id,
            "document": document,
            "metadata": metadata,
            "distance": distance,
        })
    return rows


# ---------------------------------------------------------------------------
# BM25 retrieval (simple tokenization + TF-IDF scoring)
# ---------------------------------------------------------------------------
def tokenize(text):
    """Simple whitespace + lowercasing tokenizer."""
    return re.findall(r"\w+", text.lower())


class SimpleBM25:
    """Lightweight BM25 implementation for small corpora."""

    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.corpus_tokens = []
        self.doc_freqs = defaultdict(int)
        self.doc_lengths = []
        self.avg_doc_length = 0
        self.n_docs = 0
        self.chunk_ids = []

    def fit(self, documents, chunk_ids):
        self.chunk_ids = chunk_ids
        self.n_docs = len(documents)
        total_length = 0

        for doc in documents:
            tokens = tokenize(doc)
            self.corpus_tokens.append(tokens)
            self.doc_lengths.append(len(tokens))
            total_length += len(tokens)

            # Count unique tokens per document for IDF
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freqs[token] += 1

        self.avg_doc_length = total_length / self.n_docs if self.n_docs > 0 else 0

    def _idf(self, token):
        df = self.doc_freqs.get(token, 0)
        return max(0, np.log((self.n_docs - df + 0.5) / (df + 0.5) + 1))

    def search(self, query_text, top_k):
        query_tokens = tokenize(query_text)
        scores = []

        for i in range(self.n_docs):
            doc_tokens = self.corpus_tokens[i]
            doc_len = self.doc_lengths[i]
            token_counts = defaultdict(int)
            for t in doc_tokens:
                token_counts[t] += 1

            score = 0.0
            for qt in query_tokens:
                if qt not in token_counts:
                    continue
                tf = token_counts[qt]
                idf = self._idf(qt)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * doc_len / self.avg_doc_length
                )
                score += idf * numerator / denominator

            scores.append(score)

        # Sort by score descending
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for idx in ranked_indices[:top_k]:
            results.append({
                "chunk_id": self.chunk_ids[idx],
                "bm25_score": scores[idx],
                "rank": len(results) + 1,
            })
        return results


def bm25_retrieve(bm25_index, query_text, top_k):
    return bm25_index.search(query_text, top_k)


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------
def reciprocal_rank_fusion(dense_results, bm25_results, k=RRF_K, top_n=3):
    """
    RRF_score(d) = sum(1 / (k + rank(d))) across all ranked lists.
    """
    rrf_scores = defaultdict(float)

    for rank_pos, row in enumerate(dense_results):
        chunk_id = row["chunk_id"]
        rrf_scores[chunk_id] += 1.0 / (k + rank_pos + 1)

    for rank_pos, row in enumerate(bm25_results):
        chunk_id = row["chunk_id"]
        rrf_scores[chunk_id] += 1.0 / (k + rank_pos + 1)

    # Sort by RRF score descending
    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return ranked[:top_n]


def rrf_retrieve(collection, bm25_index, question_text, top_k_dense, top_k_bm25, top_k_final):
    """Dense + BM25 → RRF fusion → top_k_final."""
    dense_results = dense_retrieve(collection, question_text, top_k_dense)
    bm25_results = bm25_retrieve(bm25_index, question_text, top_k_bm25)
    fused = reciprocal_rank_fusion(dense_results, bm25_results, k=RRF_K, top_n=top_k_final)

    results = []
    for chunk_id, rrf_score in fused:
        # Find the document from dense results or BM25 results
        doc = None
        for r in dense_results:
            if r["chunk_id"] == chunk_id:
                doc = r
                break
        if doc is None:
            for r in bm25_results:
                if r["chunk_id"] == chunk_id:
                    doc = r
                    break
        results.append({
            "chunk_id": chunk_id,
            "rrf_score": rrf_score,
            "document": doc.get("document") if doc else None,
            "metadata": doc.get("metadata") if doc else None,
        })
    return results


# ---------------------------------------------------------------------------
# Hit check
# ---------------------------------------------------------------------------
def check_hit(retrieved_ids, expected_chunk_id):
    """Check if the expected chunk_id appears in the top-3 retrieved IDs."""
    return expected_chunk_id in retrieved_ids[:3]


# ---------------------------------------------------------------------------
# Main experiment runner
# ---------------------------------------------------------------------------
def run_experiment(collection, questions, mode="baseline", bm25_index=None):
    """
    mode: 'baseline' (dense only, top_k=3) or 'after' (dense+BM25+RRF, top_k=3)
    """
    results = []
    latencies = []

    for q in questions:
        question_text = q["question"]
        expected_chunk_id = q["expected_chunk_id"]

        # Measure latency
        start = time.perf_counter()

        if mode == "baseline":
            retrieved = dense_retrieve(collection, question_text, top_k=TOP_K_BASELINE)
            retrieved_ids = [r["chunk_id"] for r in retrieved]
        else:
            # After: Dense top 25 + BM25 top 25 → RRF → top 3
            retrieved = rrf_retrieve(
                collection, bm25_index, question_text,
                top_k_dense=TOP_K_CANDIDATES,
                top_k_bm25=TOP_K_CANDIDATES,
                top_k_final=TOP_K_BASELINE,
            )
            retrieved_ids = [r["chunk_id"] for r in retrieved]

        end = time.perf_counter()
        latency_ms = (end - start) * 1000
        latencies.append(latency_ms)

        hit = check_hit(retrieved_ids, expected_chunk_id)

        results.append({
            "question": question_text,
            "expected_chunk_id": expected_chunk_id,
            "retrieved_ids": retrieved_ids,
            "hit": hit,
            "latency_ms": latency_ms,
        })

    hit_count = sum(1 for r in results if r["hit"])
    hit_rate = hit_count / len(questions) * 100
    p50_latency = statistics.median(latencies)

    return results, hit_rate, p50_latency, latencies


# ---------------------------------------------------------------------------
# Build BM25 index from collection
# ---------------------------------------------------------------------------
def build_bm25_index(collection):
    all_data = collection.get(include=["documents", "metadatas"])
    documents = all_data["documents"]
    chunk_ids = all_data["ids"]

    bm25 = SimpleBM25()
    bm25.fit(documents, chunk_ids)
    return bm25


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(name=COLLECTION_NAME)

    questions = load_golden_set()
    print(f"Loaded {len(questions)} golden questions\n")

    # Build BM25 index (needed for both baseline comparison and after)
    print("Building BM25 index...")
    bm25_index = build_bm25_index(collection)
    print(f"BM25 index built: {bm25_index.n_docs} documents\n")

    mode = sys.argv[1] if len(sys.argv) > 1 else "baseline"

    if mode == "baseline":
        print("=" * 60)
        print("BASELINE EXPERIMENT (Dense Retrieval Only, top_k=3)")
        print("=" * 60)
        results, hit_rate, p50, latencies = run_experiment(
            collection, questions, mode="baseline"
        )
    elif mode == "after":
        print("=" * 60)
        print("AFTER EXPERIMENT (Dense + BM25 + RRF, k=60, top_k=3)")
        print("=" * 60)
        results, hit_rate, p50, latencies = run_experiment(
            collection, questions, mode="after", bm25_index=bm25_index
        )
    else:
        print(f"Unknown mode: {mode}. Use 'baseline' or 'after'.")
        sys.exit(1)

    # Print results table
    print(f"\n{'Q':<4} {'Hit':<6} {'Latency':>10}  {'Expected':<45} {'Retrieved Top 3'}")
    print("-" * 130)
    for i, r in enumerate(results, 1):
        hit_str = "PASS" if r["hit"] else "FAIL"
        print(
            f"Q{i:<3} {hit_str:<6} {r['latency_ms']:>8.1f} ms  "
            f"{r['expected_chunk_id']:<45} {r['retrieved_ids']}"
        )

    print(f"\nHit-rate@3: {hit_rate:.1f}% ({sum(1 for r in results if r['hit'])}/{len(results)})")
    print(f"p50 latency: {p50:.1f} ms")
    print(f"Latencies: {[f'{l:.1f}' for l in latencies]}")

    # Save results
    output = {
        "mode": mode,
        "hit_rate": hit_rate,
        "p50_latency_ms": p50,
        "results": results,
    }
    out_path = TASK_DIR / "output" / f"week4_{mode}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nResults saved to {out_path}")
