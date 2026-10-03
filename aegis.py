import ollama

import hybrid_rerank

from action_generator import generate_action
from citation import build_citations, format_citations
from citation_validator import validate_citations
from evidence_fusion import (
    fuse_evidence,
    build_evidence_context,
)
from knowledge_gap import detect_knowledge_gap
from knowledge_guard import assess_evidence
from query_router import route_query


LLM_MODEL = "qwen3:4b"


def flatten_evidence_for_citations(evidence):
    """
    Evidence Fusion разделяет источники на current и superseded.

    Для citations сохраняем этот порядок:
    1. current evidence;
    2. superseded evidence.

    Это важно, потому что current evidence имеет authority priority.
    """
    current = evidence.get("current", [])
    superseded = evidence.get("superseded", [])

    return current + superseded


def generate_answer(query, context, citations, mode):
    citation_text = format_citations(citations)

    system_prompt = f"""
You are Aegis, an enterprise engineering knowledge assistant.

Query mode: {mode}

Use ONLY the provided evidence.

Rules:
1. Never invent facts.
2. Current evidence has priority over superseded evidence.
3. Explicit supersedes relationships are authoritative.
4. Every factual claim MUST have at least one citation ID.
5. Put citations in the same sentence as the factual claim.
6. Use citation IDs exactly as provided, for example [C1].
7. Never invent citation IDs.
8. Never cite a source that does not directly support the claim.
9. If evidence is insufficient, explicitly say that evidence is insufficient.
10. Return ONLY the final answer. Do not explain your reasoning.
11. Do not add source descriptions, citation explanations, summaries, confidence statements, or meta-commentary.
12. Do not use Markdown tables, bullet lists, LaTex, or boxed answers.
13. Write atomic claims. One sentence must contain one fact supported by its citation.
14. Do not combine facts from different documents in one sentence.
15. For comparison or change questions, write one cited sentence per source.
16. For metadata questions such as status, effective date, page, section, title, or version, answer with the exact metadata value concisely.
17. Keep the answer concise.
"""

    user_prompt = f"""
Question:
{query}

Evidence:
{context}

Available citations:
{citation_text}

Answer using only the evidence above.

Return only the final answer.

Use one short sentence per factual claim.
Put the citation at the end of that sentence.

For comparisons, write separate sentences for facts from separate sources.
Do not explain what citations mean.
Do not repeat the answer.
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


def retrieve(query):
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


def print_citation_validation(validation):
    """
    Совместим с новой и старой формой результата валидатора.
    """
    used_ids = validation.get(
        "used_ids",
        validation.get("used", []),
    )

    invalid_ids = validation.get(
        "invalid_ids",
        validation.get("invalid", []),
    )

    print()
    print("CITATION VALIDATION")
    print(f"Valid: {validation['valid']}")
    print(f"Used: {used_ids}")

    if invalid_ids:
        print(f"Invalid IDs: {invalid_ids}")

    if "citation_precision" in validation:
        print(
            "Citation Precision: "
            f"{validation['citation_precision']:.2%}"
        )

    if "claim_support_rate" in validation:
        print(
            "Claim Support Rate: "
            f"{validation['claim_support_rate']:.2%}"
        )

    if "citation_completeness" in validation:
        print(
            "Citation Completeness: "
            f"{validation['citation_completeness']:.2%}"
        )

    unsupported_claims = validation.get(
        "unsupported_claims",
        [],
    )

    if unsupported_claims:
        print("Unsupported claims:")

        for claim in unsupported_claims:
            print(f"- {claim}")

    uncited_claims = validation.get("uncited_claims", [])

    if uncited_claims:
        print("Uncited claims:")

        for claim in uncited_claims:
            print(f"- {claim}")


def run(query):
    print()
    print("=" * 70)
    print("AEGIS")
    print("=" * 70)

    # 1. ROUTE
    mode = route_query(query)

    print(f"\nQuery: {query}")
    print(f"Mode:  {mode}")

    # 2. RETRIEVE
    results = retrieve(query)

    # 3. KNOWLEDGE GUARD
    guard = assess_evidence(
        results,
        query,
    )

    print(f"Evidence: {guard['status']}")

    # 4. KNOWLEDGE GAP / SAFE REFUSAL
    if guard["status"] == "INSUFFICIENT":
        gap = detect_knowledge_gap(
            query,
            results,
            guard,
        )

        print()
        print("KNOWLEDGE GAP")
        print(gap)

        return {
            "status": "INSUFFICIENT",
            "query": query,
            "guard": guard,
            "knowledge_gap": gap,
            "answer": None,
            "citations": [],
            "validation": None,
        }

    # 5. EVIDENCE FUSION
    evidence = fuse_evidence(results)

    context = build_evidence_context(evidence)

    # 6. CITATIONS
    citation_evidence = flatten_evidence_for_citations(evidence)

    citations = build_citations(citation_evidence)

    # 7. ANSWER
    answer = generate_answer(
        query,
        context,
        citations,
        mode,
    )

    print()
    print("=" * 70)
    print("ANSWER")
    print("=" * 70)
    print(answer)

    print()
    print("=" * 70)
    print("CITATIONS")
    print("=" * 70)
    print(format_citations(citations))

    # 8. CITATION PRECISION / COMPLETENESS VALIDATION
    validation = validate_citations(
        answer,
        citations,
    )

    print_citation_validation(validation)

    # 9. ACTION
    action = generate_action(evidence)

    print()
    print("=" * 70)
    print("ACTION")
    print("=" * 70)

    print(f"Status: {action['status']}")

    for index, item in enumerate(
        action["actions"],
        start=1,
    ):
        print(
            f"{index}. "
            f"[{item['type']}] "
            f"{item['instruction']}"
        )

    return {
        "status": "SUFFICIENT",
        "query": query,
        "mode": mode,
        "guard": guard,
        "results": results,
        "evidence": evidence,
        "answer": answer,
        "citations": citations,
        "validation": validation,
        "action": action,
    }


def main():
    queries = [
        "Which pressure sensor does pump P-481 currently use?",
        "Why does pump P-481 currently use E21 instead of E17?",
        "What is the engine oil pressure of pump P-999?",
    ]

    for query in queries:
        run(query)


if __name__ == "__main__":
    main()