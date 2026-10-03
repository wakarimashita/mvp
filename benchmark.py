import time

import hybrid_rerank

from evidence_fusion import fuse_evidence
from knowledge_guard import assess_evidence
from query_router import route_query


def timed(name, function):
    start = time.perf_counter()
    result = function()
    elapsed = (time.perf_counter() - start) * 1000

    print(f"{name:<25} {elapsed:>8.1f} ms")

    return result, elapsed


def benchmark(query):
    print()
    print("=" * 70)
    print(f"QUERY: {query}")
    print("=" * 70)

    total_start = time.perf_counter()

    # Router
    _, router_ms = timed(
        "Query Router",
        lambda: route_query(query),
    )

    documents = hybrid_rerank.load_documents()

    # Vector
    vector_results, vector_ms = timed(
        "Vector Search",
        lambda: hybrid_rerank.vector_search(query),
    )

    # BM25
    keyword_results, bm25_ms = timed(
        "BM25",
        lambda: hybrid_rerank.keyword_search(
            query,
            documents,
        ),
    )

    # RRF
    hybrid_results, rrf_ms = timed(
        "RRF",
        lambda: hybrid_rerank.reciprocal_rank_fusion(
            vector_results,
            keyword_results,
        ),
    )

    # Reranker
    reranked_results, rerank_ms = timed(
        "Reranker",
        lambda: hybrid_rerank.rerank(
            query,
            hybrid_results,
        ),
    )

    # Evidence Fusion
    evidence, fusion_ms = timed(
        "Evidence Fusion",
        lambda: fuse_evidence(
            reranked_results,
        ),
    )

    # Guard
    guard, guard_ms = timed(
        "Knowledge Guard",
        lambda: assess_evidence(
            reranked_results,
            query,
        ),
    )

    total_ms = (
        time.perf_counter() - total_start
    ) * 1000

    print()
    print("-" * 70)
    print(f"TOTAL RETRIEVAL PIPELINE: {total_ms:.1f} ms")
    print(f"GUARD STATUS: {guard['status']}")
    print("-" * 70)


def main():
    queries = [
        "Which pressure sensor does pump P-481 currently use?",
        "Why does pump P-481 currently use E21 instead of E17?",
        "What is the engine oil pressure of pump P-999?",
    ]

    for query in queries:
        benchmark(query)


if __name__ == "__main__":
    main()
