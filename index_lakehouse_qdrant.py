import json
from datetime import datetime, timezone
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)


# ============================================================
# CONFIG
# ============================================================

GOLD_CHUNKS_FILE = Path(
    "local_lakehouse/gold/retrieval_chunks.jsonl"
)

OUTPUT_MANIFEST = Path(
    "local_lakehouse/gold/qdrant_index_manifest.json"
)

QDRANT_URL = "http://localhost:6333"

# Отдельная коллекция. Текущий MVP collection "aegis" не изменяется.
COLLECTION_NAME = "aegis_lakehouse"

VECTOR_SIZE = 768
UPSERT_BATCH_SIZE = 100


# ============================================================
# QDRANT
# ============================================================

client = QdrantClient(QDRANT_URL)


# ============================================================
# HELPERS
# ============================================================

def now_utc():
    """Returns an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def load_jsonl(path):
    """Loads JSON Lines rows from file."""
    rows = []

    with open(path, "r", encoding="utf-8") as file:
        for line_number, line in enumerate(
            file,
            start=1,
        ):
            line = line.strip()

            if not line:
                continue

            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON on line {line_number} "
                    f"in {path}: {error}"
                ) from error

    return rows


def create_collection():
    """
    Recreates only the Lakehouse Qdrant collection.

    This never touches the existing 'aegis' MVP collection.
    """
    if client.collection_exists(COLLECTION_NAME):
        print(
            f"Deleting existing collection "
            f"'{COLLECTION_NAME}'..."
        )

        client.delete_collection(COLLECTION_NAME)

    print(
        f"Creating collection '{COLLECTION_NAME}'..."
    )

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE,
        ),
    )


def build_payload(chunk):
    """
    Keeps vector out of payload and preserves retrieval, authority,
    provenance and future access-control metadata.
    """
    return {
        "chunk_id": chunk.get("chunk_id"),
        "document_id": chunk.get("document_id"),
        "chunk_index": chunk.get("chunk_index"),
        "text": chunk.get("text"),

        "title": chunk.get("title"),
        "document_type": chunk.get("document_type"),
        "version": chunk.get("version"),
        "effective_date": chunk.get("effective_date"),
        "status": chunk.get("status"),
        "asset_id": chunk.get("asset_id"),
        "supersedes": chunk.get("supersedes"),

        "source": chunk.get("source"),
        "page": chunk.get("page"),
        "section": chunk.get("section"),

        # Будет использован для local ACL и будущего Purview mapping.
        "access_scope": chunk.get("access_scope"),

        "document_summary": chunk.get(
            "document_summary"
        ),
        "embedding_model": chunk.get(
            "embedding_model"
        ),
        "embedding_dimensions": chunk.get(
            "embedding_dimensions"
        ),
        "ingested_at": chunk.get("ingested_at"),
        "embedded_at": chunk.get("embedded_at"),
    }


def index_chunks(chunks):
    """
    Uploads vectors and payloads to Qdrant in batches.
    """
    total = len(chunks)

    for start in range(0, total, UPSERT_BATCH_SIZE):
        batch = chunks[
            start:start + UPSERT_BATCH_SIZE
        ]

        points = []

        for offset, chunk in enumerate(batch):
            point_id = start + offset

            embedding = chunk.get("embedding", [])

            if len(embedding) != VECTOR_SIZE:
                raise ValueError(
                    f"Invalid vector size for "
                    f"{chunk.get('chunk_id')}: "
                    f"expected {VECTOR_SIZE}, "
                    f"got {len(embedding)}."
                )

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=build_payload(chunk),
                )
            )

        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True,
        )

        completed = min(
            start + UPSERT_BATCH_SIZE,
            total,
        )

        print(
            f"Indexed {completed}/{total} chunks..."
        )


def write_manifest(indexed_chunks):
    """Writes a local index manifest for reproducibility."""
    manifest = {
        "indexed_at": now_utc(),
        "collection_name": COLLECTION_NAME,
        "qdrant_url": QDRANT_URL,
        "source_file": str(GOLD_CHUNKS_FILE),
        "indexed_chunks": indexed_chunks,
        "vector_size": VECTOR_SIZE,
        "distance": "COSINE",
        "upsert_batch_size": UPSERT_BATCH_SIZE,
        "preserved_metadata": [
            "document_id",
            "chunk_id",
            "title",
            "document_type",
            "version",
            "effective_date",
            "status",
            "asset_id",
            "supersedes",
            "source",
            "page",
            "section",
            "access_scope",
        ],
    }

    with open(
        OUTPUT_MANIFEST,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            manifest,
            file,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("AEGIS LAKEHOUSE → QDRANT INDEX")
    print("=" * 70)

    if not GOLD_CHUNKS_FILE.exists():
        raise FileNotFoundError(
            "Gold retrieval chunks file not found: "
            f"{GOLD_CHUNKS_FILE.resolve()}"
        )

    print("Loading Gold retrieval chunks...")

    chunks = load_jsonl(GOLD_CHUNKS_FILE)

    if not chunks:
        raise ValueError(
            "No chunks found in Gold retrieval chunks file."
        )

    print(f"Loaded chunks: {len(chunks)}")

    dimensions = {
        len(chunk.get("embedding", []))
        for chunk in chunks
    }

    if dimensions != {VECTOR_SIZE}:
        raise ValueError(
            "Unexpected embedding dimensions in Gold data: "
            f"{sorted(dimensions)}. "
            f"Expected only {VECTOR_SIZE}."
        )

    create_collection()
    index_chunks(chunks)
    write_manifest(len(chunks))

    collection_info = client.get_collection(
        COLLECTION_NAME
    )

    print()
    print("=" * 70)
    print("LAKEHOUSE INDEXING COMPLETE")
    print("=" * 70)
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Indexed chunks: {len(chunks)}")
    print(
        "Qdrant points count: "
        f"{collection_info.points_count}"
    )
    print(f"Manifest: {OUTPUT_MANIFEST}")
    print()
    print(
        "The existing 'aegis' collection was not modified."
    )


if __name__ == "__main__":
    main()