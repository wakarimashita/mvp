import json
from pathlib import Path

import hybrid_rerank
from evidence_fusion import fuse_evidence, build_evidence_context


SERVICE_HISTORY_FILE = Path("service_history.json")


def load_service_history():
    with open(
        SERVICE_HISTORY_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def find_asset_history(asset_id):
    history = load_service_history()

    return [
        record
        for record in history
        if record.get("asset_id") == asset_id
    ]


def deep_investigate(query, asset_id):
    # ---------------------------------------------------------
    # 1. Knowledge retrieval
    # ---------------------------------------------------------

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

    reranked_results = hybrid_rerank.rerank(
        query,
        hybrid_results,
    )

    # ---------------------------------------------------------
    # 2. Evidence Fusion
    # ---------------------------------------------------------

    evidence = fuse_evidence(
        reranked_results
    )

    knowledge_context = build_evidence_context(
        evidence
    )

    # ---------------------------------------------------------
    # 3. Structured service history
    # ---------------------------------------------------------

    history = find_asset_history(
        asset_id
    )

    return {
        "knowledge": knowledge_context,
        "service_history": history,
        "conflicts": evidence["conflicts"],
    }


def print_investigation(result):
    print()
    print("=" * 70)
    print("KNOWLEDGE EVIDENCE")
    print("=" * 70)
    print(result["knowledge"])

    print()
    print("=" * 70)
    print("SERVICE HISTORY")
    print("=" * 70)

    for record in result["service_history"]:
        print(
            f"{record['date']} | "
            f"{record['type']} | "
            f"{record['description']}"
        )

    print()
    print("=" * 70)
    print("CONFLICTS")
    print("=" * 70)

    for conflict in result["conflicts"]:
        print(
            f"{conflict['old']['id']} "
            f"-> "
            f"{conflict['new']['id']}"
        )
        print(
            f"Resolution: "
            f"{conflict['resolution']}"
        )


def main():
    query = (
        "Why does pump P-481 currently use E21 "
        "instead of E17?"
    )

    result = deep_investigate(
        query=query,
        asset_id="P-481",
    )

    print_investigation(result)


if __name__ == "__main__":
    main()
