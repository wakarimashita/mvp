import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct


EMBEDDING_MODEL = "nomic-embed-text"
COLLECTION_NAME = "aegis"

# Подключаемся к локальному Qdrant
client = QdrantClient("http://localhost:6333")


documents = [
    "Pump P-481 uses pressure sensor E17.",
    "Pump P-481 requires pressure sensor E17 replacement every 5000 operating hours.",
    "Pump P-481 operating temperature is 85°C.",
    "Pump P-482 uses temperature sensor T12.",
    "The weather in Lviv is rainy today.",
]


def get_embedding(text):
    response = ollama.embed(
        model=EMBEDDING_MODEL,
        input=text,
    )

    return response["embeddings"][0]


def create_collection():
    # Удаляем старую коллекцию, если она существует
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)

    # nomic-embed-text → 768 dimensions
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=768,
            distance=Distance.COSINE,
        ),
    )


def index_documents():
    points = []

    for i, text in enumerate(documents):
        print(f"Embedding document {i + 1}/{len(documents)}...")

        vector = get_embedding(text)

        point = PointStruct(
            id=i,
            vector=vector,
            payload={
                "text": text,
            },
        )

        points.append(point)

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
    )


def search(query, limit=5):
    query_vector = get_embedding(query)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit,
    ).points

    print()
    print(f"Query: {query}")
    print()
    print("Results:")

    for rank, result in enumerate(results, start=1):
        print(f"{rank}. score={result.score:.4f}")
        print(f"   {result.payload['text']}")
        print()


def main():
    create_collection()
    index_documents()

    search(
        "What is the operating temperature of pump P-481?"
    )


if __name__ == "__main__":
    main()
