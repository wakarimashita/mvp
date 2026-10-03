import ollama

from hybrid_rerank import (
    vector_search,
    keyword_search,
    reciprocal_rank_fusion,
    rerank,
)

LLM_MODEL = "qwen3:4b"


def fuse_evidence(results):
    """
    Resolve conflicts using document metadata.

    Reranker tells us what is relevant.
    Evidence Fusion tells us which evidence has authority.
    """

    current = []
    superseded = []
    conflicts = []

    # Index documents by ID
    documents = {
        result["id"]: result["metadata"]
        for result in results
    }

    for result in results:
        metadata = result["metadata"]

        if metadata.get("status") == "current":
            current.append(result)

        elif metadata.get("status") == "superseded":
            superseded.append(result)

    # Detect explicit supersession relationships
    for new_doc in current:
        supersedes_id = new_doc["metadata"].get("supersedes")

        if supersedes_id and supersedes_id in documents:
            old_doc = next(
                result
                for result in results
                if result["id"] == supersedes_id
            )

            conflicts.append({
                "old": old_doc,
                "new": new_doc,
                "resolution": "new document explicitly supersedes old document",
            })

    return {
        "current": current,
        "superseded": superseded,
        "conflicts": conflicts,
    }


def build_evidence_context(evidence):
    parts = []

    for result in evidence["current"]:
        metadata = result["metadata"]

        parts.append(
            "[CURRENT EVIDENCE]\n"
            f"Source: {metadata['source']}\n"
            f"Document: {metadata['title']}\n"
            f"Version: {metadata['version']}\n"
            f"Effective date: {metadata['effective_date']}\n"
            f"Status: {metadata['status']}\n"
            f"Page: {metadata['page']}\n"
            f"Section: {metadata['section']}\n"
            f"Text: {result['text']}"
        )

    for result in evidence["superseded"]:
        metadata = result["metadata"]

        parts.append(
            "[SUPERSEDED EVIDENCE]\n"
            f"Source: {metadata['source']}\n"
            f"Document: {metadata['title']}\n"
            f"Version: {metadata['version']}\n"
            f"Effective date: {metadata['effective_date']}\n"
            f"Status: {metadata['status']}\n"
            f"Page: {metadata['page']}\n"
            f"Section: {metadata['section']}\n"
            f"Text: {result['text']}"
        )

    for conflict in evidence["conflicts"]:
        old_doc = conflict["old"]["metadata"]
        new_doc = conflict["new"]["metadata"]

        parts.append(
            "[CONFLICT RESOLUTION]\n"
            f"Old document: {old_doc['title']} "
            f"v{old_doc['version']}\n"
            f"New document: {new_doc['title']} "
            f"v{new_doc['version']}\n"
            f"Resolution: {conflict['resolution']}"
        )

    return "\n\n".join(parts)


def generate_answer(query, context):
    system_prompt = """
You are Aegis, an engineering knowledge assistant.

Answer using ONLY the provided evidence.

Rules:
1. Current evidence has priority over superseded evidence.
2. If a current document explicitly supersedes an older document,
   use the current document as the authoritative answer.
3. Mention important conflicts when they exist.
4. Cite the source document and page.
5. Never invent facts.
6. If the evidence cannot resolve the question, say so.
7. Keep the answer concise.
"""

    user_prompt = f"""
Question:
{query}

Evidence:
{context}

Answer the question using the evidence above.
"""

    response = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    )

    return response["message"]["content"]


def main():
    query = "Which pressure sensor does pump P-481 currently use?"

    # Retrieval
    vector_results = vector_search(query)
    keyword_results = keyword_search(
        query,
        # hybrid_rerank loads documents internally,
        # so retrieve them from the module
        __import__("hybrid_rerank").load_documents(),
    )

    # Hybrid retrieval
    hybrid_results = reciprocal_rank_fusion(
        vector_results,
        keyword_results,
    )

    # Relevance ranking
    reranked_results = rerank(
        query,
        hybrid_results,
    )

    # Evidence reasoning
    evidence = fuse_evidence(reranked_results)

    # Build normalized evidence package
    context = build_evidence_context(evidence)

    print()
    print("=" * 70)
    print("EVIDENCE PACKAGE")
    print("=" * 70)
    print(context)

    # Generate final answer
    answer = generate_answer(
        query,
        context,
    )

    print()
    print("=" * 70)
    print("AEGIS ANSWER")
    print("=" * 70)
    print(answer)


if __name__ == "__main__":
    main()
