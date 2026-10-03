import json
from pathlib import Path

import ollama

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
)


# ============================================================
# CONFIG
# ============================================================

EMBEDDING_MODEL = "nomic-embed-text"

COLLECTION_NAME = "aegis"

QDRANT_URL = "http://localhost:6333"

DOCUMENTS_DIR = Path("documents")

VECTOR_SIZE = 768


# ============================================================
# QDRANT
# ============================================================

client = QdrantClient(QDRANT_URL)


# ============================================================
# EMBEDDING
# ============================================================

def get_embedding(text):

    response = ollama.embed(
        model=EMBEDDING_MODEL,
        input=text,
    )

    return response["embeddings"][0]


# ============================================================
# LOAD DOCUMENTS
# ============================================================

def load_documents():

    documents = []

    for path in DOCUMENTS_DIR.glob("*.json"):

        print(f"Loading {path}...")

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            document = json.load(file)

        documents.append(document)

    return documents


# ============================================================
# CREATE COLLECTION
# ============================================================

def create_collection():

    if client.collection_exists(
        COLLECTION_NAME
    ):

        print(
            f"Deleting existing collection "
            f"'{COLLECTION_NAME}'..."
        )

        client.delete_collection(
            COLLECTION_NAME
        )

    print(
        f"Creating collection "
        f"'{COLLECTION_NAME}'..."
    )

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE,
        ),
    )


# ============================================================
# INDEX DOCUMENTS
# ============================================================

def index_documents(documents):

    points = []

    for index, document in enumerate(
        documents
    ):

        print(
            f"Embedding "
            f"{index + 1}/{len(documents)}: "
            f"{document['id']}"
        )

        text = document["text"]

        vector = get_embedding(text)

        payload = {
            "text": document["text"],
            "id": document["id"],
            "title": document["title"],
            "version": document["version"],
            "effective_date": document["effective_date"],
            "status": document["status"],
            "asset_id": document["asset_id"],
            "supersedes": document["supersedes"],
            "source": document["source"],
            "page": document["page"],
            "section": document["section"],
        }

        point = PointStruct(
            id=index,
            vector=vector,
            payload=payload,
        )

        points.append(point)

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("AEGIS KNOWLEDGE INGESTION")
    print("=" * 70)

    documents = load_documents()

    print()
    print(
        f"Found {len(documents)} documents."
    )

    create_collection()

    index_documents(
        documents
    )

    print()
    print("=" * 70)
    print("INGESTION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
