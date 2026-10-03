import json
from pathlib import Path

import ollama

from deep_investigation import deep_investigate


LLM_MODEL = "qwen3:4b"


def build_deep_context(result):
    parts = []

    parts.append(
        "=== KNOWLEDGE BASE ===\n"
        + result["knowledge"]
    )

    parts.append("=== SERVICE HISTORY ===")

    for record in result["service_history"]:
        parts.append(
            f"Date: {record['date']}\n"
            f"Type: {record['type']}\n"
            f"Description: {record['description']}\n"
            + "\n".join(
                f"{key}: {value}"
                for key, value in record.items()
                if key not in {
                    "id",
                    "date",
                    "type",
                    "description",
                }
            )
        )

    if result["conflicts"]:
        parts.append("=== CONFLICT RESOLUTION ===")

        for conflict in result["conflicts"]:
            old_doc = conflict["old"]["metadata"]
            new_doc = conflict["new"]["metadata"]

            parts.append(
                f"Older document: "
                f"{old_doc['title']} v{old_doc['version']}\n"
                f"Newer document: "
                f"{new_doc['title']} v{new_doc['version']}\n"
                f"Resolution: {conflict['resolution']}"
            )

    return "\n\n".join(parts)


def generate_answer(query, context):
    system_prompt = """
You are Aegis, an enterprise engineering investigation assistant.

Your task is to answer questions by combining multiple evidence sources.

Use ONLY the provided evidence.

Rules:

1. Do not invent facts.
2. Prefer current documents over superseded documents.
3. Use explicit supersedes relationships when available.
4. Use service history as factual operational evidence.
5. Connect events only when the evidence supports the connection.
6. Clearly distinguish:
   - documented facts
   - inferred relationships
7. When documents conflict, explain the conflict and its resolution.
8. Cite the relevant document, version and page.
9. Mention relevant service-history dates.
10. If the evidence is insufficient, say so.
11. Keep the answer concise but explanatory.
"""

    user_prompt = f"""
Question:
{query}

Evidence Package:
{context}

Provide a concise engineering investigation answer.
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
    query = (
        "Why does pump P-481 currently use E21 "
        "instead of E17?"
    )

    result = deep_investigate(
        query=query,
        asset_id="P-481",
    )

    context = build_deep_context(result)

    print()
    print("=" * 70)
    print("EVIDENCE PACKAGE SENT TO LLM")
    print("=" * 70)
    print(context)

    answer = generate_answer(
        query,
        context,
    )

    print()
    print("=" * 70)
    print("DEEP INVESTIGATION ANSWER")
    print("=" * 70)
    print(answer)


if __name__ == "__main__":
    main()
