import hybrid_rerank

from knowledge_guard import (
    assess_evidence,
    print_guard_result,
)


def search(query):
    documents = hybrid_rerank.load_documents()

    vector_results = hybrid_rerank.vector_search(query)

    keyword_results = hybrid_rerank.keyword_search(
        query,
        documents,
    )

    hybrid_results = hybrid_rerank.reciprocal_rank_fusion(
        vector_results,
        keyword_results,
    )

    return hybrid_rerank.rerank(
        query,
        hybrid_results,
    )


def main():
    queries = [
        "Which pressure sensor does pump P-481 use?",
        "What is the engine oil pressure of P-999?",
    ]

    for query in queries:
        print()
        print("=" * 70)
        print(f"QUERY: {query}")
        print("=" * 70)

        results = search(query)

        guard = assess_evidence(
            results,
            query,
        )

        print_guard_result(guard)


if __name__ == "__main__":
    main()
