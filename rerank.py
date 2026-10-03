from sentence_transformers import CrossEncoder


MODEL = "BAAI/bge-reranker-v2-m3"


query = "Which sensor is used by pump P-481?"

documents = [
    "Pump P-481 uses pressure sensor E17.",
    "Pump P-481 operating temperature is 85°C.",
    "Pump P-482 uses temperature sensor T12.",
    "Pump P-481 requires pressure sensor E17 replacement every 5000 operating hours.",
    "The weather in Lviv is rainy today.",
]


def main():
    print("Loading reranker model...")
    model = CrossEncoder(MODEL)

    pairs = [
        [query, document]
        for document in documents
    ]

    scores = model.predict(pairs)

    results = []

    for document, score in zip(documents, scores):
        results.append({
            "text": document,
            "score": float(score),
        })

    results.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    print()
    print("=" * 60)
    print("RERANKER")
    print("=" * 60)

    for rank, result in enumerate(results, start=1):
        print(
            f"{rank}. "
            f"score={result['score']:.4f}"
        )
        print(
            f"   {result['text']}"
        )


if __name__ == "__main__":
    main()
