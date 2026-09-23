import re

from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder


RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CANDIDATES_PER_RETRIEVER = 10
RRF_K = 60

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

cross_encoder = CrossEncoder(RERANKER_MODEL)


def _tokenize(text):
    return _TOKEN_PATTERN.findall(text.lower())


def _dense_search(collection, question_embedding, top_k, where=None):
    query_kwargs = {
        "query_embeddings": [question_embedding],
        "n_results": min(top_k, collection.count()),
    }
    if where:
        query_kwargs["where"] = where
    results = collection.query(**query_kwargs)
    return results["ids"][0]


def _sparse_search(all_ids, all_documents, question, top_k):
    bm25 = BM25Okapi([_tokenize(document) for document in all_documents])
    scores = bm25.get_scores(_tokenize(question))

    ranked_indices = sorted(
        range(len(all_ids)), key=lambda index: scores[index], reverse=True
    )
    return [all_ids[index] for index in ranked_indices[:top_k]]


def _reciprocal_rank_fusion(ranked_id_lists, k=RRF_K):
    scores = {}

    for ranked_ids in ranked_id_lists:
        for rank, doc_id in enumerate(ranked_ids):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

    return sorted(scores, key=scores.get, reverse=True)


def _rerank(question, candidate_ids, id_to_document, top_k):
    if not candidate_ids:
        return []

    pairs = [(question, id_to_document[doc_id]) for doc_id in candidate_ids]
    scores = cross_encoder.predict(pairs)

    reranked = sorted(zip(candidate_ids, scores), key=lambda item: item[1], reverse=True)
    results = []
    for rank, (doc_id, score) in enumerate(
        reranked[:top_k],
        start=1,
    ):
        results.append(
            {
                "rank": rank,
                "chunk_id": doc_id,
                "score": float(score),
                "text": id_to_document[doc_id],
            }
        )

    return results


def hybrid_retrieve(collection, question, question_embedding, top_k=3, where=None):
    """Dense (vector) + sparse (BM25) retrieval, fused with Reciprocal Rank
    Fusion, then narrowed to `top_k` with a cross-encoder reranker.

    `where` is an optional Chroma metadata filter (e.g. {"sdk_version": "v3"}),
    applied to both the dense candidate pool and the sparse (BM25) candidate
    pool. Omitting it preserves the original unfiltered behavior."""
    if collection.count() == 0:
        return []

    get_kwargs = {"include": ["documents"]}
    if where:
        get_kwargs["where"] = where
    all_data = collection.get(**get_kwargs)
    all_ids, all_documents = all_data["ids"], all_data["documents"]

    if not all_ids:
        return []

    id_to_document = dict(zip(all_ids, all_documents))

    dense_ids = _dense_search(collection, question_embedding, CANDIDATES_PER_RETRIEVER, where=where)
    sparse_ids = _sparse_search(all_ids, all_documents, question, CANDIDATES_PER_RETRIEVER)

    fused_ids = _reciprocal_rank_fusion([dense_ids, sparse_ids])

    return _rerank(question, fused_ids, id_to_document, top_k)
