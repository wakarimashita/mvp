import json
from pathlib import Path

import ollama

from qdrant_client import QdrantClient
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder


# ============================================================
# CONFIG
# ============================================================

EMBEDDING_MODEL = "nomic-embed-text"

RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

COLLECTION_NAME = "aegis"

QDRANT_URL = "http://localhost:6333"

DOCUMENTS_DIR = Path("documents")

RETRIEVAL_LIMIT = 10

RERANK_LIMIT = 5

RRF_K = 60


# ============================================================
# CLIENT
# ============================================================

qdrant = QdrantClient(
    QDRANT_URL
)


# ============================================================
# LOAD DOCUMENTS
# ============================================================

def load_documents():

    documents = []

    for path in DOCUMENTS_DIR.glob("*.json"):

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            documents.append(
                json.load(file)
            )

    return documents


# ============================================================
# EMBEDDING
# ============================================================

def get_embedding(text):

    response = ollama.embed(
        model=EMBEDDING_MODEL,
        input=text,
    )

    return response["embeddings"][0]


# ============================================================
# TOKENIZATION
# ============================================================

def tokenize(text):

    return text.lower().split()


# ============================================================
# VECTOR SEARCH
# ============================================================

def vector_search(
    query,
    limit=RETRIEVAL_LIMIT,
):

    query_vector = get_embedding(
        query
    )

    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit,
    ).points

    return results


# ============================================================
# BM25
# ============================================================

def keyword_search(
    query,
    documents,
):

    tokenized_documents = [
        tokenize(document["text"])
        for document in documents
    ]

    bm25 = BM25Okapi(
        tokenized_documents
    )

    query_tokens = tokenize(
        query
    )

    scores = bm25.get_scores(
        query_tokens
    )

    results = []

    for index, score in enumerate(
        scores
    ):

        results.append(
            {
                "index": index,
                "score": float(score),
                "document": documents[index],
            }
        )

    results.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    return results[
        :RETRIEVAL_LIMIT
    ]


# ============================================================
# RRF
# ============================================================

def reciprocal_rank_fusion(
    vector_results,
    keyword_results,
    k=RRF_K,
):

    scores = {}

    # --------------------------------------------------------
    # Vector results
    # --------------------------------------------------------

    for rank, result in enumerate(
        vector_results,
        start=1,
    ):

        document_id = (
            result.payload["id"]
        )

        if document_id not in scores:

            scores[document_id] = {
                "id": document_id,
                "text": result.payload["text"],
                "vector_rank": None,
                "keyword_rank": None,
                "vector_score": None,
                "keyword_score": None,
                "rrf_score": 0.0,
                "metadata": result.payload,
            }

        scores[
            document_id
        ]["vector_rank"] = rank

        scores[
            document_id
        ]["vector_score"] = float(
            result.score
        )

        scores[
            document_id
        ]["rrf_score"] += (
            1 / (k + rank)
        )

    # --------------------------------------------------------
    # BM25 results
    # --------------------------------------------------------

    for rank, result in enumerate(
        keyword_results,
        start=1,
    ):

        document_id = (
            result["document"]["id"]
        )

        if document_id not in scores:

            scores[document_id] = {
                "id": document_id,
                "text": result["document"]["text"],
                "vector_rank": None,
                "keyword_rank": None,
                "vector_score": None,
                "keyword_score": None,
                "rrf_score": 0.0,
                "metadata": result["document"],
            }

        scores[
            document_id
        ]["keyword_rank"] = rank

        scores[
            document_id
        ]["keyword_score"] = result[
            "score"
        ]

        scores[
            document_id
        ]["rrf_score"] += (
            1 / (k + rank)
        )

    return sorted(
        scores.values(),
        key=lambda x: x["rrf_score"],
        reverse=True,
    )


# ============================================================
# RERANK
# ============================================================

def rerank(
    query,
    candidates,
    limit=RERANK_LIMIT,
):

    model = CrossEncoder(
        RERANKER_MODEL
    )

    candidates = candidates[
        :limit
    ]

    pairs = [
        [
            query,
            candidate["text"],
        ]
        for candidate in candidates
    ]

    scores = model.predict(
        pairs
    )

    results = []

    for candidate, score in zip(
        candidates,
        scores,
    ):

        result = candidate.copy()

        result[
            "reranker_score"
        ] = float(score)

        results.append(
            result
        )

    results.sort(
        key=lambda x: x[
            "reranker_score"
        ],
        reverse=True,
    )

    return results


# ============================================================
# PRINT
# ============================================================

def print_results(
    title,
    results,
):

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

    for rank, result in enumerate(
        results,
        start=1,
    ):

        print(
            f"{rank}. "
            f"{result['text']}"
        )

        print(
            f"   id={result['id']}"
        )

        metadata = result[
            "metadata"
        ]

        print(
            f"   asset={metadata.get('asset_id')}"
        )

        print(
            f"   document={metadata.get('title')}"
        )

        print(
            f"   version={metadata.get('version')}"
        )

        print(
            f"   effective={metadata.get('effective_date')}"
        )

        print(
            f"   status={metadata.get('status')}"
        )

        print(
            f"   source={metadata.get('source')}"
        )

        print(
            f"   page={metadata.get('page')}"
        )

        print()


# ============================================================
# MAIN
# ============================================================

def main():

    query = (
        "Which pressure sensor "
        "does pump P-481 currently use?"
    )

    documents = load_documents()

    print()
    print("=" * 70)
    print("AEGIS RETRIEVAL")
    print("=" * 70)

    print(
        f"Documents loaded: "
        f"{len(documents)}"
    )

    print(
        f"Query: {query}"
    )

    # --------------------------------------------------------
    # Vector
    # --------------------------------------------------------

    vector_results = vector_search(
        query
    )

    # --------------------------------------------------------
    # BM25
    # --------------------------------------------------------

    keyword_results = keyword_search(
        query,
        documents,
    )

    # --------------------------------------------------------
    # RRF
    # --------------------------------------------------------

    hybrid_results = (
        reciprocal_rank_fusion(
            vector_results,
            keyword_results,
        )
    )

    print_results(
        "RRF RESULTS",
        hybrid_results,
    )

    # --------------------------------------------------------
    # Reranker
    # --------------------------------------------------------

    reranked_results = rerank(
        query,
        hybrid_results,
    )

    print_results(
        "RERANKED RESULTS",
        reranked_results,
    )


if __name__ == "__main__":
    main()
