import json

import hybrid_rerank

from knowledge_guard import assess_evidence


DATASET = "golden_questions.json"


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


def evaluate_question(item):
    query = item["question"]

    results = search(query)

    guard = assess_evidence(
        results,
        query,
    )

    status_correct = (
        guard["status"]
        == item["expected_status"]
    )

    expected_status = item["expected_status"]
    actual_status = guard["status"]

    source_correct = True

    if item["expected_source"]:
        retrieved_ids = [
            result["id"]
            for result in results
        ]

        source_correct = (
            item["expected_source"]
            in retrieved_ids
        )

    return {
        "id": item["id"],
        "question": query,
        "expected_status": expected_status,
        "actual_status": actual_status,
        "status_correct": status_correct,
        "source_correct": source_correct,
        "top_result": (
            results[0]["id"]
            if results
            else None
        ),
        "reranker_score": (
            results[0]["reranker_score"]
            if results
            else 0.0
        ),
    }


def main():
    with open(
        DATASET,
        "r",
        encoding="utf-8",
    ) as file:
        dataset = json.load(file)

    results = []

    for item in dataset:
        print(
            f"Evaluating {item['id']}: "
            f"{item['question']}"
        )

        result = evaluate_question(item)

        results.append(result)

    total = len(results)

    status_accuracy = sum(
        result["status_correct"]
        for result in results
    ) / total

    source_accuracy = sum(
        result["source_correct"]
        for result in results
    ) / total

    print()
    print("=" * 70)
    print("AEGIS EVALUATION")
    print("=" * 70)

    for result in results:
        print()
        print(result["id"])
        print(
            f"  status correct: "
            f"{result['status_correct']}"
        )
        print(
            f"  expected status: "
            f"{result['expected_status']}"
        )
        print(
            f"  actual status:   "
            f"{result['actual_status']}"
        )
        print(
            f"  source correct: "
            f"{result['source_correct']}"
        )
        print(
            f"  top result: "
            f"{result['top_result']}"
        )
        print(
            f"  reranker score: "
            f"{result['reranker_score']:.4f}"
        )

    print()
    print("=" * 70)
    print(
        f"Status accuracy: "
        f"{status_accuracy:.2%}"
    )
    print(
        f"Source retrieval accuracy: "
        f"{source_accuracy:.2%}"
    )


if __name__ == "__main__":
    main()
