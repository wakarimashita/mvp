import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import ollama


# ============================================================
# CONFIG
# ============================================================

SOURCE_DIR = Path("synthetic_source")

SOURCE_UNSTRUCTURED_DIR = SOURCE_DIR / "unstructured"
SOURCE_STRUCTURED_DIR = SOURCE_DIR / "structured"

LAKEHOUSE_DIR = Path("local_lakehouse")

BRONZE_DIR = LAKEHOUSE_DIR / "bronze"
SILVER_DIR = LAKEHOUSE_DIR / "silver"
GOLD_DIR = LAKEHOUSE_DIR / "gold"

BRONZE_UNSTRUCTURED_DIR = BRONZE_DIR / "unstructured"
BRONZE_STRUCTURED_DIR = BRONZE_DIR / "structured"

EMBEDDING_MODEL = "nomic-embed-text"

# Документы в synthetic corpus короткие, но pipeline поддерживает
# полноценное chunking для будущих больших документов.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120

# Ollama умеет принимать список строк в input.
EMBEDDING_BATCH_SIZE = 16


# ============================================================
# GENERAL HELPERS
# ============================================================

def now_utc():
    """Returns UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    """Writes formatted JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


def write_jsonl(path, rows):
    """Writes rows in JSON Lines format."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        for row in rows:
            file.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
                + "\n"
            )


def read_json(path):
    """Reads one JSON file."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def read_csv(path):
    """Reads a CSV table as a list of dictionaries."""
    with open(path, "r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def copy_source_file(source, destination):
    """Copies a source file while preserving metadata."""
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(source, destination)


# ============================================================
# BRONZE LAYER
# ============================================================

def build_bronze_layer():
    """
    Bronze layer preserves raw synthetic source files.

    Future Fabric equivalent:
    - OneLake files / Lakehouse Bronze tables
    - scheduled pipeline copy activity
    """
    print()
    print("Building Bronze layer...")

    if BRONZE_DIR.exists():
        shutil.rmtree(BRONZE_DIR)

    BRONZE_UNSTRUCTURED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    BRONZE_STRUCTURED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    unstructured_files = sorted(
        SOURCE_UNSTRUCTURED_DIR.glob("*.json")
    )

    structured_files = sorted(
        SOURCE_STRUCTURED_DIR.glob("*.csv")
    )

    for source_path in unstructured_files:
        copy_source_file(
            source_path,
            BRONZE_UNSTRUCTURED_DIR / source_path.name,
        )

    for source_path in structured_files:
        copy_source_file(
            source_path,
            BRONZE_STRUCTURED_DIR / source_path.name,
        )

    manifest = {
        "layer": "bronze",
        "refreshed_at": now_utc(),
        "unstructured_files": len(unstructured_files),
        "structured_files": len(structured_files),
        "source_unstructured_dir": str(
            SOURCE_UNSTRUCTURED_DIR
        ),
        "source_structured_dir": str(
            SOURCE_STRUCTURED_DIR
        ),
    }

    write_json(
        BRONZE_DIR / "ingestion_manifest.json",
        manifest,
    )

    print(
        f"  Raw unstructured files: "
        f"{len(unstructured_files)}"
    )
    print(
        f"  Raw structured tables: "
        f"{len(structured_files)}"
    )

    return manifest


# ============================================================
# SILVER LAYER: NORMALIZED DOCUMENTS AND CHUNKS
# ============================================================

def normalize_whitespace(text):
    """Normalizes whitespace without changing content."""
    return " ".join(str(text or "").split())


def chunk_text(text, chunk_size, overlap):
    """
    Splits text into overlapping chunks.

    The synthetic documents are short, so most create one chunk.
    This is intentional: the same code supports longer manuals later.
    """
    text = normalize_whitespace(text)

    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = min(
            start + chunk_size,
            len(text),
        )

        # Prefer breaking on whitespace for readability.
        if end < len(text):
            last_space = text.rfind(" ", start, end)

            if last_space > start:
                end = last_space

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = max(end - overlap, start + 1)

    return chunks


def normalize_document(document, ingested_at):
    """
    Creates the normalized Silver documents schema.

    This is the local equivalent of a normalized Lakehouse documents table.
    """
    return {
        "document_id": document["id"],
        "title": document.get("title"),
        "document_type": document.get("document_type"),
        "version": document.get("version"),
        "effective_date": document.get("effective_date"),
        "status": document.get("status"),
        "asset_id": document.get("asset_id"),
        "supersedes": document.get("supersedes"),
        "source": document.get("source"),
        "page": document.get("page"),
        "section": document.get("section"),
        "access_scope": document.get(
            "access_scope",
            "engineering",
        ),
        "summary": document.get("summary"),
        "text": normalize_whitespace(
            document.get("text", "")
        ),
        "ingested_at": ingested_at,
    }


def build_chunks(normalized_document):
    """
    Builds normalized Silver chunks.

    Each chunk retains all provenance and access metadata needed for:
    - retrieval;
    - citation;
    - authority resolution;
    - access filtering;
    - future Azure AI Search indexing.
    """
    text_chunks = chunk_text(
        normalized_document["text"],
        CHUNK_SIZE,
        CHUNK_OVERLAP,
    )

    chunks = []

    for index, text in enumerate(text_chunks, start=1):
        chunks.append({
            "chunk_id": (
                f"{normalized_document['document_id']}"
                f"-chunk-{index:03d}"
            ),
            "document_id": normalized_document[
                "document_id"
            ],
            "chunk_index": index,
            "text": text,

            # Metadata / provenance copied into every chunk.
            "title": normalized_document["title"],
            "document_type": normalized_document[
                "document_type"
            ],
            "version": normalized_document["version"],
            "effective_date": normalized_document[
                "effective_date"
            ],
            "status": normalized_document["status"],
            "asset_id": normalized_document["asset_id"],
            "supersedes": normalized_document[
                "supersedes"
            ],
            "source": normalized_document["source"],
            "page": normalized_document["page"],
            "section": normalized_document["section"],
            "access_scope": normalized_document[
                "access_scope"
            ],
            "document_summary": normalized_document[
                "summary"
            ],
            "ingested_at": normalized_document[
                "ingested_at"
            ],
        })

    return chunks


def build_silver_layer():
    """
    Builds normalized documents, chunks and structured operational tables.

    Future Fabric equivalent:
    - Bronze files -> Silver Delta tables
    """
    print()
    print("Building Silver layer...")

    if SILVER_DIR.exists():
        shutil.rmtree(SILVER_DIR)

    SILVER_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    ingested_at = now_utc()

    documents = []
    chunks = []

    source_files = sorted(
        BRONZE_UNSTRUCTURED_DIR.glob("*.json")
    )

    for index, path in enumerate(
        source_files,
        start=1,
    ):
        document = read_json(path)

        normalized_document = normalize_document(
            document,
            ingested_at,
        )

        documents.append(normalized_document)

        document_chunks = build_chunks(
            normalized_document
        )

        chunks.extend(document_chunks)

        if index % 100 == 0:
            print(
                f"  Normalized {index}/"
                f"{len(source_files)} documents..."
            )

    write_jsonl(
        SILVER_DIR / "documents.jsonl",
        documents,
    )

    write_jsonl(
        SILVER_DIR / "chunks.jsonl",
        chunks,
    )

    summaries = [
        {
            "document_id": document["document_id"],
            "title": document["title"],
            "document_type": document["document_type"],
            "asset_id": document["asset_id"],
            "status": document["status"],
            "summary": document["summary"],
            "ingested_at": document["ingested_at"],
        }
        for document in documents
    ]

    write_jsonl(
        SILVER_DIR / "document_summaries.jsonl",
        summaries,
    )

    structured_table_counts = {}

    for source_path in sorted(
        BRONZE_STRUCTURED_DIR.glob("*.csv")
    ):
        rows = read_csv(source_path)

        output_path = (
            SILVER_DIR / source_path.name
        )

        copy_source_file(
            source_path,
            output_path,
        )

        structured_table_counts[
            source_path.stem
        ] = len(rows)

    manifest = {
        "layer": "silver",
        "refreshed_at": now_utc(),
        "documents": len(documents),
        "chunks": len(chunks),
        "document_summaries": len(summaries),
        "structured_tables": structured_table_counts,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
    }

    write_json(
        SILVER_DIR / "transformation_manifest.json",
        manifest,
    )

    print(f"  Normalized documents: {len(documents)}")
    print(f"  Normalized chunks: {len(chunks)}")
    print(f"  Document summaries: {len(summaries)}")

    for name, count in structured_table_counts.items():
        print(f"  Structured table {name}: {count}")

    return documents, chunks, manifest


# ============================================================
# GOLD LAYER: EMBEDDINGS AND RETRIEVAL-READY CHUNKS
# ============================================================

def get_embeddings(texts):
    """
    Creates embeddings for a batch with Ollama nomic-embed-text.
    """
    response = ollama.embed(
        model=EMBEDDING_MODEL,
        input=texts,
    )

    embeddings = response.get("embeddings", [])

    if len(embeddings) != len(texts):
        raise RuntimeError(
            "Embedding count does not match input count. "
            f"Expected {len(texts)}, got {len(embeddings)}."
        )

    return embeddings


def build_gold_layer(chunks):
    """
    Builds retrieval-ready chunks with embeddings.

    Future Fabric / Azure equivalent:
    - Gold Lakehouse table with embeddings;
    - sync to Azure AI Search vector index.
    """
    print()
    print("Building Gold layer and embeddings...")

    if GOLD_DIR.exists():
        shutil.rmtree(GOLD_DIR)

    GOLD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    retrieval_chunks = []

    total_batches = (
        len(chunks) + EMBEDDING_BATCH_SIZE - 1
    ) // EMBEDDING_BATCH_SIZE

    for batch_number, start in enumerate(
        range(0, len(chunks), EMBEDDING_BATCH_SIZE),
        start=1,
    ):
        batch = chunks[
            start:start + EMBEDDING_BATCH_SIZE
        ]

        texts = [
            chunk["text"]
            for chunk in batch
        ]

        embeddings = get_embeddings(texts)

        for chunk, embedding in zip(
            batch,
            embeddings,
        ):
            retrieval_chunk = {
                **chunk,
                "embedding_model": EMBEDDING_MODEL,
                "embedding_dimensions": len(embedding),
                "embedding": embedding,
                "embedded_at": now_utc(),
            }

            retrieval_chunks.append(retrieval_chunk)

        print(
            f"  Embedded batch {batch_number}/"
            f"{total_batches} "
            f"({len(retrieval_chunks)}/{len(chunks)} chunks)"
        )

    write_jsonl(
        GOLD_DIR / "retrieval_chunks.jsonl",
        retrieval_chunks,
    )

    gold_manifest = {
        "layer": "gold",
        "refreshed_at": now_utc(),
        "retrieval_chunks": len(retrieval_chunks),
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimensions": (
            retrieval_chunks[0]["embedding_dimensions"]
            if retrieval_chunks
            else 0
        ),
        "source": "silver/chunks.jsonl",
    }

    write_json(
        GOLD_DIR / "gold_manifest.json",
        gold_manifest,
    )

    print(
        f"  Retrieval-ready chunks: "
        f"{len(retrieval_chunks)}"
    )
    print(
        f"  Embedding dimensions: "
        f"{gold_manifest['embedding_dimensions']}"
    )

    return gold_manifest


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("AEGIS LOCAL LAKEHOUSE PIPELINE")
    print("=" * 70)

    if not SOURCE_DIR.exists():
        raise FileNotFoundError(
            f"Source directory not found: "
            f"{SOURCE_DIR.resolve()}"
        )

    if not SOURCE_UNSTRUCTURED_DIR.exists():
        raise FileNotFoundError(
            "Unstructured source directory not found: "
            f"{SOURCE_UNSTRUCTURED_DIR.resolve()}"
        )

    if not SOURCE_STRUCTURED_DIR.exists():
        raise FileNotFoundError(
            "Structured source directory not found: "
            f"{SOURCE_STRUCTURED_DIR.resolve()}"
        )

    bronze_manifest = build_bronze_layer()

    documents, chunks, silver_manifest = (
        build_silver_layer()
    )

    gold_manifest = build_gold_layer(chunks)

    pipeline_manifest = {
        "pipeline": "AEGIS local Lakehouse-style pipeline",
        "completed_at": now_utc(),
        "bronze": bronze_manifest,
        "silver": silver_manifest,
        "gold": gold_manifest,
    }

    write_json(
        LAKEHOUSE_DIR / "pipeline_manifest.json",
        pipeline_manifest,
    )

    print()
    print("=" * 70)
    print("LOCAL LAKEHOUSE PIPELINE COMPLETE")
    print("=" * 70)
    print(f"Bronze: {BRONZE_DIR}")
    print(f"Silver: {SILVER_DIR}")
    print(f"Gold:   {GOLD_DIR}")
    print()
    print(
        "This local structure maps to the future Fabric flow:"
    )
    print(
        "scheduled Fabric pipeline -> Bronze -> Silver -> Gold "
        "Lakehouse tables -> Azure AI Search."
    )


if __name__ == "__main__":
    main()