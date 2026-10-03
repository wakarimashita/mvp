import ollama

from qdrant_client import QdrantClient
from rank_bm25 import BM25Okapi


EMBEDDING_MODEL = "nomic-embed-text"
COLLECTION_NAME = "aegis"

QDRANT_URL = "http://localhost:6333"


# ---------------------------------------------------------
# Documents
# ---------------------------------------------------------

documents = [
    "Pump P-481 uses pressure sensor E17.",
    "Pump P-481 requires pressure sensor E17 replacement every 5000 operating hours.",
    "Pump P-481 operating temperature is 85°C.",
    "Pump P-482 uses temperature sensor T12.",
    "The weather in Lviv is rainy today.",
]


# ---------------------------------------------------------
# Clients
# ---------------------------------------------------------

client = QdrantClient(QDRANT_URL)


# ---------------------------------------------------------
# Embeddings
# ---------------------------------------------------------

def get_embedding(text):
    response = ollama.embed(
        model=EMBEDDING_MODEL,
        input=text,
    )

    return response["embeddings"][0]


# ---------------------------------------------------------
# Tokenization
# ---------------------------------------------------------

def tokenize(text):
    return text.lower().split()


# ---------------------------------------------------------
# Vector Search
# ---------------------------------------------------------

def vector_search(query, limit=5):

    query_vector = get_embedding(query)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit,
    ).points

    return results


# ---------------------------------------------------------
# Keyword Search (BM25)
# ---------------------------------------------------------

def keyword_search(query):

    tokenized_documents = [
        tokenize(document)
        for document in documents
    ]

    bm25 = BM25Okapi(tokenized_documents)

    query_tokens = tokenize(query)

    scores = bm25.get_scores(query_tokens)

    results = []

    for index, score in enumerate(scores):

        results.append(
            {
                "index": index,
                "score": float(score),
                "text": documents[index],
            }
        )

    results.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    return results


# ---------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------

def reciprocal_rank_fusion(
    vector_results,
    keyword_results,
    k=60,
):

    scores = {}

    # ---------------------------------------------
    # Vector ranking
    # ---------------------------------------------

    for rank, result in enumerate(
        vector_results,
        start=1,
    ):

        text = result.payload["text"]

        if text not in scores:

            scores[text] = {
                "text": text,
                "vector_rank": None,
                "keyword_rank": None,
                "rrf_score": 0.0,
            }

        scores[text]["vector_rank"] = rank

        scores[text]["rrf_score"] += (
            1 / (k + rank)
        )

    # ---------------------------------------------
    # BM25 ranking
    # ---------------------------------------------

    for rank, result in enumerate(
        keyword_results,
        start=1,
    ):

        text = result["text"]

        if text not in scores:

            scores[text] = {
                "text": text,
                "vector_rank": None,
                "keyword_rank": None,
                "rrf_score": 0.0,
            }

        scores[text]["keyword_rank"] = rank

        scores[text]["rrf_score"] += (
            1 / (k + rank)
        )

    # ---------------------------------------------
    # Sort by RRF score
    # ---------------------------------------------

    return sorted(
        scores.values(),
        key=lambda x: x["rrf_score"],
        reverse=True,
    )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    query = "Which sensor is used by pump P-481?"


    # =====================================================
    # VECTOR SEARCH
    # =====================================================

    print("=" * 60)
    print("VECTOR SEARCH")
    print("=" * 60)

    vector_results = vector_search(query)

    for rank, result in enumerate(
        vector_results,
        start=1,
    ):

        print(
            f"{rank}. "
            f"score={result.score:.4f} "
            f"{result.payload['text']}"
        )


    # =====================================================
    # KEYWORD SEARCH
    # =====================================================

    print()
    print("=" * 60)
    print("KEYWORD SEARCH (BM25)")
    print("=" * 60)

    keyword_results = keyword_search(query)

    for rank, result in enumerate(
        keyword_results,
        start=1,
    ):

        print(
            f"{rank}. "
            f"score={result['score']:.4f} "
            f"{result['text']}"
        )


    # =====================================================
    # HYBRID SEARCH
    # =====================================================

    print()
    print("=" * 60)
    print("HYBRID SEARCH (RRF)")
    print("=" * 60)

    hybrid_results = reciprocal_rank_fusion(
        vector_results,
        keyword_results,
    )

    for rank, result in enumerate(
        hybrid_results,
        start=1,
    ):

        print(
            f"{rank}. "
            f"RRF={result['rrf_score']:.6f} "
            f"vector_rank={result['vector_rank']} "
            f"keyword_rank={result['keyword_rank']}"
        )

        print(
            f"   {result['text']}"
        )


if __name__ == "__main__":
    main()
