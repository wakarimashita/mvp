def detect_knowledge_gap(query, results, guard):
    """
    Convert insufficient retrieval into a structured
    knowledge gap.
    """

    if guard["status"] == "SUFFICIENT":
        return None

    asset_id = None

    if results:
        asset_id = (
            results[0]
            .get("metadata", {})
            .get("asset_id")
        )

    return {
        "type": "MISSING_EVIDENCE",
        "query": query,
        "asset_id": asset_id,
        "reason": guard["reason"],
        "retrieved_documents": [
            {
                "id": result["id"],
                "title": result["metadata"].get("title"),
                "score": result.get(
                    "reranker_score",
                    0.0,
                ),
            }
            for result in results[:3]
        ],
        "recommended_sources": [
            "service manual",
            "service bulletin",
            "maintenance history",
            "engineering specification",
        ],
    }


def print_gap(gap):
    if not gap:
        print("No knowledge gap detected.")
        return

    print()
    print("=" * 70)
    print("KNOWLEDGE GAP")
    print("=" * 70)

    print(f"Type: {gap['type']}")
    print(f"Query: {gap['query']}")
    print(f"Asset: {gap['asset_id']}")
    print(f"Reason: {gap['reason']}")

    print()
    print("Retrieved documents:")

    for document in gap["retrieved_documents"]:
        print(
            f"  - {document['title']} "
            f"({document['id']}) "
            f"score={document['score']:.4f}"
        )

    print()
    print("Recommended sources:")

    for source in gap["recommended_sources"]:
        print(f"  - {source}")


if __name__ == "__main__":
    # Standalone test
    guard = {
        "status": "INSUFFICIENT",
        "reason": "No relevant evidence found.",
    }

    results = [
        {
            "id": "doc-something",
            "reranker_score": 0.05,
            "metadata": {
                "title": "Pump P-481 Manual",
                "asset_id": "P-481",
            },
        }
    ]

    gap = detect_knowledge_gap(
        "What is the maximum operating pressure of P-481?",
        results,
        guard,
    )

    print_gap(gap)
