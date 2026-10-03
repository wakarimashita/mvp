import json
import re
import sys
import time
from pathlib import Path

import ollama
from qdrant_client import QdrantClient
from rank_bm25 import BM25Okapi


# ============================================================
# CONFIG
# ============================================================

GOLD_CHUNKS_FILE = Path(
    "local_lakehouse/gold/retrieval_chunks.jsonl"
)

QDRANT_URL = "http://localhost:6333"

COLLECTION_NAME = "aegis_lakehouse"

EMBEDDING_MODEL = "nomic-embed-text"

VECTOR_TOP_K = 20
KEYWORD_TOP_K = 20
FINAL_TOP_K = 5

# Keeps all vector/BM25 candidates before schema-aware reranking.
FUSION_CANDIDATE_LIMIT = VECTOR_TOP_K + KEYWORD_TOP_K

RRF_K = 60


# ============================================================
# CLIENT
# ============================================================

client = QdrantClient(QDRANT_URL)


# ============================================================
# LOADING
# ============================================================

def load_jsonl(path):
    """Loads JSON Lines into a list of dictionaries."""
    rows = []

    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if line:
                rows.append(json.loads(line))

    return rows


def tokenize(text):
    """
    Lightweight tokenizer for local BM25.

    Keeps IDs such as:
    - p-481
    - e21
    - sb-1001
    """
    text = str(text or "").lower()

    tokens = []
    current = ""

    for character in text:
        if character.isalnum() or character == "-":
            current += character
        else:
            if current:
                tokens.append(current)
                current = ""

    if current:
        tokens.append(current)

    return tokens


def load_search_index():
    """
    Loads Gold chunks and creates an in-memory BM25 index.

    Future Azure mapping:
    Azure AI Search handles both vector and keyword search.
    """
    if not GOLD_CHUNKS_FILE.exists():
        raise FileNotFoundError(
            "Gold chunks file not found: "
            f"{GOLD_CHUNKS_FILE.resolve()}"
        )

    chunks = load_jsonl(GOLD_CHUNKS_FILE)

    if not chunks:
        raise ValueError("No Gold chunks found.")

    corpus = []

    for chunk in chunks:
        searchable_text = " ".join([
            str(chunk.get("title", "")),
            str(chunk.get("document_type", "")),
            str(chunk.get("asset_id", "")),
            str(chunk.get("section", "")),
            str(chunk.get("status", "")),
            str(chunk.get("document_summary", "")),
            str(chunk.get("text", "")),
        ])

        corpus.append(tokenize(searchable_text))

    bm25 = BM25Okapi(corpus)

    chunk_by_id = {
        chunk["chunk_id"]: chunk
        for chunk in chunks
    }

    return chunks, chunk_by_id, bm25


# ============================================================
# QUERY UNDERSTANDING
# ============================================================

def detect_asset_id(query):
    """Extracts asset IDs such as P-481, P-1001, and P-1010."""
    match = re.search(r"\bP-\d+\b", query.upper())

    return match.group(0) if match else None


def infer_search_intent(query):
    """
    Determines which document type should be preferred.
    """
    query_lower = query.lower()

    current_configuration_terms = [
        "currently use",
        "currently installed",
        "current configuration",
        "current sensor",
        "installed sensor",
        "replacement sensor",
        "replacement",
        "superseded",
    ]

    troubleshooting_terms = [
        "troubleshooting",
        "troubleshoot",
        "diagnose",
        "diagnostic",
        "intermittent",
        "fault",
        "symptom",
        "guidance",
    ]

    work_instruction_terms = [
        "work instruction",
        "inspection procedure",
        "inspection steps",
        "how to inspect",
        "how to perform",
    ]

    if any(term in query_lower for term in current_configuration_terms):
        return "current_configuration"

    if any(term in query_lower for term in troubleshooting_terms):
        return "troubleshooting"

    if any(term in query_lower for term in work_instruction_terms):
        return "work_instruction"

    return None


# ============================================================
# VECTOR SEARCH
# ============================================================

def get_embedding(query):
    """Creates one query embedding with Ollama."""
    response = ollama.embed(
        model=EMBEDDING_MODEL,
        input=query,
    )

    return response["embeddings"][0]


def query_qdrant(vector, limit):
    """
    Queries Qdrant.

    Supports both newer and older qdrant-client APIs.
    """
    try:
        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return response.points

    except AttributeError:
        return client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )


def vector_search(query):
    """
    Returns vector-ranked results and embedding/vector-search timings.
    """
    embedding_start = time.perf_counter()

    vector = get_embedding(query)

    embedding_ms = (
        time.perf_counter() - embedding_start
    ) * 1000

    search_start = time.perf_counter()

    hits = query_qdrant(
        vector=vector,
        limit=VECTOR_TOP_K,
    )

    vector_search_ms = (
        time.perf_counter() - search_start
    ) * 1000

    results = []

    for hit in hits:
        payload = dict(hit.payload or {})

        results.append({
            "chunk_id": payload.get("chunk_id"),
            "document_id": payload.get("document_id"),
            "score": float(hit.score),
            "payload": payload,
        })

    return results, {
        "query_embedding_ms": round(embedding_ms, 2),
        "vector_search_ms": round(vector_search_ms, 2),
    }


# ============================================================
# BM25 KEYWORD SEARCH
# ============================================================

def keyword_search(query, chunks, bm25):
    """Returns BM25-ranked chunks."""
    query_tokens = tokenize(query)

    scores = bm25.get_scores(query_tokens)

    ranked_indices = sorted(
        range(len(chunks)),
        key=lambda index: scores[index],
        reverse=True,
    )

    results = []

    for index in ranked_indices[:KEYWORD_TOP_K]:
        chunk = chunks[index]

        results.append({
            "chunk_id": chunk["chunk_id"],
            "document_id": chunk["document_id"],
            "score": float(scores[index]),
            "payload": chunk,
        })

    return results


# ============================================================
# HYBRID RRF
# ============================================================

def reciprocal_rank_fusion(vector_results, keyword_results):
    """
    Combines vector and BM25 rankings using Reciprocal Rank Fusion.

    Returns all fused candidates before final reranking.
    """
    fused_scores = {}
    result_by_chunk_id = {}

    for rank, result in enumerate(
        vector_results,
        start=1,
    ):
        chunk_id = result["chunk_id"]

        result_by_chunk_id[chunk_id] = result

        fused_scores[chunk_id] = (
            fused_scores.get(chunk_id, 0.0)
            + 1 / (RRF_K + rank)
        )

    for rank, result in enumerate(
        keyword_results,
        start=1,
    ):
        chunk_id = result["chunk_id"]

        result_by_chunk_id[chunk_id] = result

        fused_scores[chunk_id] = (
            fused_scores.get(chunk_id, 0.0)
            + 1 / (RRF_K + rank)
        )

    ranked_chunk_ids = sorted(
        fused_scores,
        key=fused_scores.get,
        reverse=True,
    )

    results = []

    for chunk_id in ranked_chunk_ids[:FUSION_CANDIDATE_LIMIT]:
        result = result_by_chunk_id[chunk_id].copy()
        result["rrf_score"] = fused_scores[chunk_id]

        results.append(result)

    return results


# ============================================================
# ASSET CANDIDATE EXPANSION
# ============================================================

def add_exact_asset_candidates(query, fused_results, chunks):
    """
    Ensures that documents for an explicitly named asset are available
    to the schema-aware reranker.

    Vector and BM25 retrieval remain the primary retrieval path.
    This only adds metadata-matched candidates when the query explicitly
    contains an asset ID such as P-1001.
    """
    requested_asset_id = detect_asset_id(query)

    if not requested_asset_id:
        return fused_results

    candidate_by_chunk_id = {
        result["chunk_id"]: result
        for result in fused_results
    }

    for chunk in chunks:
        if chunk.get("asset_id") != requested_asset_id:
            continue

        chunk_id = chunk["chunk_id"]

        if chunk_id not in candidate_by_chunk_id:
            candidate_by_chunk_id[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": chunk.get("document_id"),
                "score": 0.0,
                "payload": chunk,
                "rrf_score": 0.0,
                "asset_candidate_added": True,
            }

    return list(candidate_by_chunk_id.values())


# ============================================================
# SCHEMA-AWARE RERANKING
# ============================================================

def apply_schema_aware_reranking(query, results):
    """
    Reranks hybrid-retrieval candidates using Gold metadata.

    Rules:
    - Exact asset ID matches receive a strong deterministic boost.
    - Current-configuration questions prefer service bulletins.
    - Troubleshooting questions prefer troubleshooting notes.
    - Inspection/procedure questions prefer work instructions.
    - Superseded documents are penalized for current-state questions.
    """
    requested_asset_id = detect_asset_id(query)
    intent = infer_search_intent(query)

    preferred_type_by_intent = {
        "current_configuration": "service_bulletin",
        "troubleshooting": "troubleshooting_note",
        "work_instruction": "work_instruction",
    }

    preferred_document_type = preferred_type_by_intent.get(intent)

    for result in results:
        payload = result.get("payload", {})

        result_asset_id = payload.get("asset_id")
        document_type = payload.get("document_type")
        document_status = payload.get("status")

        base_rrf_score = result.get("rrf_score", 0.0)
        schema_boost = 0.0

        # An asset ID explicitly supplied by the user is a deterministic
        # metadata constraint and must outweigh semantic similarity from
        # documents belonging to another asset.
        if (
            requested_asset_id
            and result_asset_id == requested_asset_id
        ):
            schema_boost += 0.100

        # Prefer the document type corresponding to the user intent.
        if (
            preferred_document_type
            and document_type == preferred_document_type
        ):
            schema_boost += 0.020

        # Service bulletins are the authoritative source for current
        # installed/currently used component configuration.
        if (
            intent == "current_configuration"
            and document_type == "service_bulletin"
        ):
            schema_boost += 0.010

        # Prefer active documents for current-state questions.
        if (
            intent == "current_configuration"
            and document_status == "current"
        ):
            schema_boost += 0.005

        # Legacy manuals should not outrank current service bulletins for
        # questions explicitly asking for current configuration.
        if (
            intent == "current_configuration"
            and document_status == "superseded"
        ):
            schema_boost -= 0.010

        result["base_rrf_score"] = base_rrf_score
        result["schema_boost"] = schema_boost
        result["final_score"] = base_rrf_score + schema_boost
        result["detected_asset_id"] = requested_asset_id
        result["detected_intent"] = intent

    return sorted(
        results,
        key=lambda result: result["final_score"],
        reverse=True,
    )


# ============================================================
# FAST HYBRID SEARCH
# ============================================================

def search(query, chunks, bm25):
    """
    FAST retrieval mode.

    Includes:
    - query embedding;
    - Qdrant vector search;
    - local BM25 keyword search;
    - Reciprocal Rank Fusion;
    - exact asset candidate expansion;
    - schema-aware metadata reranking.

    Excludes:
    - cross-encoder reranking;
    - LLM generation;
    - NLI citation validation.
    """
    total_start = time.perf_counter()

    vector_results, vector_timings = vector_search(query)

    keyword_start = time.perf_counter()

    keyword_results = keyword_search(
        query=query,
        chunks=chunks,
        bm25=bm25,
    )

    keyword_ms = (
        time.perf_counter() - keyword_start
    ) * 1000

    rrf_start = time.perf_counter()

    fused_results = reciprocal_rank_fusion(
        vector_results=vector_results,
        keyword_results=keyword_results,
    )

    fused_results = add_exact_asset_candidates(
        query=query,
        fused_results=fused_results,
        chunks=chunks,
    )

    rrf_ms = (
        time.perf_counter() - rrf_start
    ) * 1000

    rerank_start = time.perf_counter()

    reranked_results = apply_schema_aware_reranking(
        query=query,
        results=fused_results,
    )

    rerank_ms = (
        time.perf_counter() - rerank_start
    ) * 1000

    results = reranked_results[:FINAL_TOP_K]

    total_ms = (
        time.perf_counter() - total_start
    ) * 1000

    timings = {
        **vector_timings,
        "keyword_search_ms": round(keyword_ms, 2),
        "rrf_ms": round(rrf_ms, 2),
        "schema_rerank_ms": round(rerank_ms, 2),
        "total_fast_retrieval_ms": round(total_ms, 2),
    }

    return results, timings


# ============================================================
# PRINTING
# ============================================================

def print_results(query, results, timings):
    """Prints human-readable retrieval output."""
    print()
    print("=" * 70)
    print("AEGIS LAKEHOUSE FAST HYBRID RETRIEVAL")
    print("=" * 70)
    print(f"Query: {query}")

    print()
    print("QUERY UNDERSTANDING")
    print(
        f"  Detected asset:  "
        f"{results[0].get('detected_asset_id') if results else None}"
    )
    print(
        f"  Detected intent: "
        f"{results[0].get('detected_intent') if results else None}"
    )

    print()
    print("LATENCY")
    print(
        f"  Query embedding: "
        f"{timings['query_embedding_ms']:.2f} ms"
    )
    print(
        f"  Vector search:   "
        f"{timings['vector_search_ms']:.2f} ms"
    )
    print(
        f"  BM25 search:     "
        f"{timings['keyword_search_ms']:.2f} ms"
    )
    print(
        f"  RRF fusion:      "
        f"{timings['rrf_ms']:.2f} ms"
    )
    print(
        f"  Schema rerank:   "
        f"{timings['schema_rerank_ms']:.2f} ms"
    )
    print(
        f"  TOTAL FAST:      "
        f"{timings['total_fast_retrieval_ms']:.2f} ms"
    )

    print()
    print("RESULTS")

    for rank, result in enumerate(
        results,
        start=1,
    ):
        payload = result["payload"]

        print()
        print(f"{rank}. {payload.get('title')}")
        print(
            f"   document_id: {payload.get('document_id')}"
        )
        print(
            f"   chunk_id:    {payload.get('chunk_id')}"
        )
        print(
            f"   asset_id:    {payload.get('asset_id')}"
        )
        print(
            f"   type:        {payload.get('document_type')}"
        )
        print(
            f"   status:      {payload.get('status')}"
        )
        print(
            f"   retrieval:   "
            f"{result.get('score', 0.0):.4f}"
        )
        print(
            f"   RRF base:    "
            f"{result.get('base_rrf_score', 0.0):.4f}"
        )
        print(
            f"   schema boost:"
            f"{result.get('schema_boost', 0.0):.4f}"
        )
        print(
            f"   final score: "
            f"{result.get('final_score', 0.0):.4f}"
        )
        print(
            f"   text:        {payload.get('text')}"
        )


# ============================================================
# MAIN
# ============================================================

def main():
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = (
            "Which pressure sensor does pump P-481 "
            "currently use?"
        )

    print("Loading Gold chunks and building BM25 index...")

    chunks, _, bm25 = load_search_index()

    print(f"Loaded chunks: {len(chunks)}")

    results, timings = search(
        query=query,
        chunks=chunks,
        bm25=bm25,
    )

    print_results(
        query=query,
        results=results,
        timings=timings,
    )


if __name__ == "__main__":
    main()