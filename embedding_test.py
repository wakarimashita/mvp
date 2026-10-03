import ollama
import math


MODEL = "nomic-embed-text"

texts = {
    "A": "Pump P-481 uses pressure sensor E17.",
    "B": "Pressure sensor E17 is installed on pump P-481.",
    "C": "The weather in Lviv is rainy today.",
}


def cosine_similarity(a, b):
    dot_product = sum(x * y for x, y in zip(a, b))

    magnitude_a = math.sqrt(sum(x * x for x in a))
    magnitude_b = math.sqrt(sum(y * y for y in b))

    return dot_product / (magnitude_a * magnitude_b)


def get_embedding(text):
    response = ollama.embed(
        model=MODEL,
        input=text,
    )

    return response["embeddings"][0]


def main():
    embeddings = {}

    # Generate embeddings
    for name, text in texts.items():
        embedding = get_embedding(text)
        embeddings[name] = embedding

        print(f"{name}:")
        print(f"  Text: {text}")
        print(f"  Dimensions: {len(embedding)}")
        print(f"  First 5 values: {embedding[:5]}")
        print()

    # Compare similarities
    print("Cosine similarity:")
    print()

    pairs = [
        ("A", "B"),
        ("A", "C"),
        ("B", "C"),
    ]

    for a, b in pairs:
        similarity = cosine_similarity(
            embeddings[a],
            embeddings[b],
        )

        print(f"{a} <-> {b}: {similarity:.4f}")


if __name__ == "__main__":
    main()
