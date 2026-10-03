import ollama

from hybrid_rerank import (
    vector_search,
    keyword_search,
    reciprocal_rank_fusion,
    rerank,
)


LLM_MODEL = "qwen3:4b"

TOP_K = 2


def build_context(results):
    """
    Convert retrieved documents into context for the LLM.
    """

    context_parts = []

    for index, result in enumerate(
        results,
        start=1,
    ):
        context_parts.append(
            f"[Evidence {index}]\n"
            f"{result['text']}"
        )

    return "\n\n".join(context_parts)


def generate_answer(query, context):

    system_prompt = """
You are an engineering knowledge assistant.

Answer the user's question using ONLY the provided evidence.

Rules:

1. Do not invent facts.
2. If the evidence does not contain the answer, say:
   "The available knowledge does not contain enough information to answer this."
3. Keep the answer concise.
4. Mention the relevant evidence when possible.
"""

    user_prompt = f"""
Question:
{query}

Evidence:
{context}

Answer the question using only the evidence above.
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

    query = "Which sensor is used by pump P-481?"

    print("=" * 70)
    print("QUERY")
    print("=" * 70)

    print(query)

    # --------------------------------------------------------
    # 1. Vector search
    # --------------------------------------------------------

    vector_results = vector_search(query)

    # --------------------------------------------------------
    # 2. BM25
    # --------------------------------------------------------

    keyword_results = keyword_search(query)

    # --------------------------------------------------------
    # 3. RRF
    # --------------------------------------------------------

    hybrid_results = reciprocal_rank_fusion(
        vector_results,
        keyword_results,
    )

    # --------------------------------------------------------
    # 4. Reranking
    # --------------------------------------------------------

    reranked_results = rerank(
        query,
        hybrid_results,
    )

    # --------------------------------------------------------
    # 5. Select final evidence
    # --------------------------------------------------------

    evidence = reranked_results[:TOP_K]

    # --------------------------------------------------------
    # 6. Build LLM context
    # --------------------------------------------------------

    context = build_context(
        evidence
    )

    print()
    print("=" * 70)
    print("EVIDENCE SENT TO LLM")
    print("=" * 70)

    print(context)

    # --------------------------------------------------------
    # 7. Generate answer
    # --------------------------------------------------------

    answer = generate_answer(
        query,
        context,
    )

    print()
    print("=" * 70)
    print("ANSWER")
    print("=" * 70)

    print(answer)


if __name__ == "__main__":
    main()
