import re


def route_query(query):
    query_lower = query.lower()

    deep_patterns = [
        r"\bпочему\b",
        r"\bwhy\b",
        r"\bcompare\b",
        r"\bсравни\b",
        r"\bразниц",
        r"\bпочему измен",
        r"\bчто измен",
        r"\bизменил",
        r"\bзамен",
        r"\bконфликт",
        r"\bconflict",
        r"\bистори",
        r"\bhistory\b",
        r"\bсвяз",
        r"\brelated\b",
    ]

    for pattern in deep_patterns:
        if re.search(pattern, query_lower):
            return "DEEP"

    exact_patterns = [
        r"какой .* у ",
        r"какое .* у ",
        r"what .* does ",
        r"which .* does ",
        r"где .* находится",
        r"what is ",
        r"which is ",
    ]

    for pattern in exact_patterns:
        if re.search(pattern, query_lower):
            return "EXACT"

    return "FAST"


def main():
    test_queries = [
        "Which pressure sensor does pump P-481 currently use?",
        "Why does pump P-481 currently use E21?",
        "What changed in the P-481 pressure sensor configuration?",
        "Which documents are related to P-481?",
        "Tell me about pump P-481",
    ]

    print("=" * 70)
    print("AEGIS QUERY ROUTER")
    print("=" * 70)

    for query in test_queries:
        mode = route_query(query)

        print()
        print(f"Query: {query}")
        print(f"Mode:  {mode}")


if __name__ == "__main__":
    main()
