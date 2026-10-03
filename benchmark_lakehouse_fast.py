import json
import math
from datetime import datetime, timezone
from pathlib import Path

import lakehouse_search


# ============================================================
# CONFIG
# ============================================================

RUNS_PER_QUERY = 3

WARMUP_QUERY = (
    "Which pressure sensor does pump P-481 currently use?"
)

OUTPUT_FILE = Path(
    "local_lakehouse/gold/fast_retrieval_benchmark.json"
)

# 20 realistic queries across the 1,000-document synthetic corpus.
# P-481 maps to SB-1001.
# P-1001 maps to SB-1002.
# P-1002 maps to SB-1003, etc.
QUERIES = [
    {
        "id": "b001",
        "query": (
            "Which pressure sensor does pump P-481 "
            "currently use?"
        ),
        "expected_asset_id": "P-481",
        "expected_document_id": "doc-sb-1001",
    },
    {
        "id": "b002",
        "query": (
            "What service bulletin supersedes the P-481 manual?"
        ),
        "expected_asset_id": "P-481",
        "expected_document_id": "doc-sb-1001",
    },
    {
        "id": "b003",
        "query": (
            "Which pressure sensor did the old P-481 manual specify?"
        ),
        "expected_asset_id": "P-481",
        "expected_document_id": "doc-p-481-manual-v1",
    },
    {
        "id": "b004",
        "query": (
            "Find troubleshooting guidance for pump P-481."
        ),
        "expected_asset_id": "P-481",
        "expected_document_id": "doc-p-481-troubleshooting",
    },
    {
        "id": "b005",
        "query": (
            "Find the pressure sensor inspection work instruction "
            "for pump P-481."
        ),
        "expected_asset_id": "P-481",
        "expected_document_id": "doc-p-481-work-instruction",
    },
    {
        "id": "b006",
        "query": (
            "Which pressure sensor does pump P-1001 "
            "currently use?"
        ),
        "expected_asset_id": "P-1001",
        "expected_document_id": "doc-sb-1002",
    },
    {
        "id": "b007",
        "query": (
            "What bulletin supersedes the service manual "
            "for pump P-1001?"
        ),
        "expected_asset_id": "P-1001",
        "expected_document_id": "doc-sb-1002",
    },
    {
        "id": "b008",
        "query": (
            "Find the legacy pressure sensor configuration "
            "for pump P-1001."
        ),
        "expected_asset_id": "P-1001",
        "expected_document_id": "doc-p-1001-manual-v1",
    },
    {
        "id": "b009",
        "query": (
            "Find troubleshooting instructions for "
            "intermittent pressure readings on pump P-1001."
        ),
        "expected_asset_id": "P-1001",
        "expected_document_id": "doc-p-1001-troubleshooting",
    },
    {
        "id": "b010",
        "query": (
            "Find the pressure sensor inspection procedure "
            "for pump P-1001."
        ),
        "expected_asset_id": "P-1001",
        "expected_document_id": "doc-p-1001-work-instruction",
    },
    {
        "id": "b011",
        "query": (
            "Which pressure sensor does pump P-1002 "
            "currently use?"
        ),
        "expected_asset_id": "P-1002",
        "expected_document_id": "doc-sb-1003",
    },
    {
        "id": "b012",
        "query": (
            "What current service bulletin applies "
            "to pump P-1002?"
        ),
        "expected_asset_id": "P-1002",
        "expected_document_id": "doc-sb-1003",
    },
    {
        "id": "b013",
        "query": (
            "What did the old service manual say about "
            "the pressure sensor on pump P-1002?"
        ),
        "expected_asset_id": "P-1002",
        "expected_document_id": "doc-p-1002-manual-v1",
    },
    {
        "id": "b014",
        "query": (
            "Find troubleshooting information for pump P-1002."
        ),
        "expected_asset_id": "P-1002",
        "expected_document_id": "doc-p-1002-troubleshooting",
    },
    {
        "id": "b015",
        "query": (
            "Find the work instruction for inspecting "
            "the pressure sensor on pump P-1002."
        ),
        "expected_asset_id": "P-1002",
        "expected_document_id": "doc-p-1002-work-instruction",
    },
    {
        "id": "b016",
        "query": (
            "Which pressure sensor does pump P-1010 "
            "currently use?"
        ),
        "expected_asset_id": "P-1010",
        "expected_document_id": "doc-sb-1011",
    },
    {
        "id": "b017",
        "query": (
            "Which document supersedes the manual "
            "for pump P-1010?"
        ),
        "expected_asset_id": "P-1010",
        "expected_document_id": "doc-sb-1011",
    },
    {
        "id": "b018",
        "query": (
            "Find the legacy manual for pump P-1010."
        ),
        "expected_asset_id": "P-1010",
        "expected_document_id": "doc-p-1010-manual-v1",
    },
    {
        "id": "b019",
        "query": (
            "Find troubleshooting guidance for pump P-1010."
        ),
        "expected_asset_id": "P-1010",
        "expected_document_id": "doc-p-1010-troubleshooting",
    },
    {
        "id": "b020",
        "query": (
            "Find the inspection procedure for "
            "pump P-1010 pressure sensor."
        ),
        "expected_asset_id": "P-1010",
        "expected_document_id": "doc-p-1010-work-instruction",
    },
]


# ============================================================
# HELPERS
# ============================================================

def now_utc():
    """Returns an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def percentile(values, percentile_value):
    """
    Calculates nearest-rank percentile without external dependencies.
    """
    if not values:
        return 0.0

    sorted_values = sorted(values)

    rank = math.ceil(
        (percentile_value / 100) * len(sorted_values)
    )

    rank = max(1, min(rank, len(sorted_values)))

    return sorted_values[rank - 1]


def average(values):
    """Returns arithmetic mean or zero for an empty list."""
    if not values:
        return 0.0

    return sum(values) / len(values)


def top_result_matches(result, expected_asset_id, expected_document_id):
    """
    Checks retrieval correctness of the first result.

    Latency requirement and retrieval correctness are reported separately.
    """
    if not result:
        return False

    payload = result.get("payload", {})

    return (
        payload.get("asset_id") == expected_asset_id
        and payload.get("document_id") == expected_document_id
    )


def round_metrics(timings):
    """Rounds timing values for readable JSON output."""
    return {
        name: round(value, 2)
        for name, value in timings.items()
    }


# ============================================================
# BENCHMARK
# ============================================================

def run_warmup(chunks, bm25):
    """
    Makes one request before measurements.

    This prevents model/server startup from distorting p95 results.
    """
    print("Running warmup query...")

    _, timings = lakehouse_search.search(
        query=WARMUP_QUERY,
        chunks=chunks,
        bm25=bm25,
    )

    print(
        "Warmup complete: "
        f"{timings['total_fast_retrieval_ms']:.2f} ms"
    )


def benchmark_query(item, chunks, bm25):
    """
    Runs one benchmark query multiple times.
    """
    runs = []

    for run_number in range(1, RUNS_PER_QUERY + 1):
        results, timings = lakehouse_search.search(
            query=item["query"],
            chunks=chunks,
            bm25=bm25,
        )

        top_result = results[0] if results else None

        top_payload = (
            top_result.get("payload", {})
            if top_result
            else {}
        )

        top_result_correct = top_result_matches(
            result=top_result,
            expected_asset_id=item["expected_asset_id"],
            expected_document_id=item["expected_document_id"],
        )

        run = {
            "run": run_number,
            "timings_ms": round_metrics(timings),
            "top_result_correct": top_result_correct,
            "top_document_id": top_payload.get("document_id"),
            "top_asset_id": top_payload.get("asset_id"),
            "top_document_type": top_payload.get("document_type"),
            "top_status": top_payload.get("status"),
            "top_title": top_payload.get("title"),
            "detected_asset_id": (
                top_result.get("detected_asset_id")
                if top_result
                else None
            ),
            "detected_intent": (
                top_result.get("detected_intent")
                if top_result
                else None
            ),
            "top_rrf_score": round(
                top_result.get("base_rrf_score", 0.0),
                6,
            ) if top_result else None,
            "top_schema_boost": round(
                top_result.get("schema_boost", 0.0),
                6,
            ) if top_result else None,
            "top_final_score": round(
                top_result.get("final_score", 0.0),
                6,
            ) if top_result else None,
        }

        runs.append(run)

        print(
            f"  run {run_number}/{RUNS_PER_QUERY}: "
            f"{timings['total_fast_retrieval_ms']:.2f} ms "
            f"| top={top_payload.get('document_id')} "
            f"| type={top_payload.get('document_type')} "
            f"| correct={top_result_correct}"
        )

    total_latencies = [
        run["timings_ms"]["total_fast_retrieval_ms"]
        for run in runs
    ]

    return {
        "id": item["id"],
        "query": item["query"],
        "expected_asset_id": item["expected_asset_id"],
        "expected_document_id": item[
            "expected_document_id"
        ],
        "runs": runs,
        "summary": {
            "top_1_accuracy": round(
                average([
                    1.0
                    if run["top_result_correct"]
                    else 0.0
                    for run in runs
                ]),
                4,
            ),
            "total_fast_retrieval_ms": {
                "min": round(min(total_latencies), 2),
                "mean": round(average(total_latencies), 2),
                "max": round(max(total_latencies), 2),
            },
        },
    }


def aggregate_metrics(results):
    """Calculates p50/p95 over all measured query runs."""
    all_runs = [
        run
        for result in results
        for run in result["runs"]
    ]

    metric_names = [
        "query_embedding_ms",
        "vector_search_ms",
        "keyword_search_ms",
        "rrf_ms",
        "schema_rerank_ms",
        "total_fast_retrieval_ms",
    ]

    latency_metrics = {}

    for metric_name in metric_names:
        values = [
            run["timings_ms"][metric_name]
            for run in all_runs
        ]

        latency_metrics[metric_name] = {
            "count": len(values),
            "min": round(min(values), 2),
            "mean": round(average(values), 2),
            "p50": round(percentile(values, 50), 2),
            "p95": round(percentile(values, 95), 2),
            "max": round(max(values), 2),
        }

    top_1_accuracy = average([
        1.0
        if run["top_result_correct"]
        else 0.0
        for run in all_runs
    ])

    p95_total = latency_metrics[
        "total_fast_retrieval_ms"
    ]["p95"]

    failed_queries = []

    for result in results:
        successful_runs = sum(
            1
            for run in result["runs"]
            if run["top_result_correct"]
        )

        if successful_runs != RUNS_PER_QUERY:
            first_run = result["runs"][0]

            failed_queries.append({
                "id": result["id"],
                "query": result["query"],
                "expected_document_id": (
                    result["expected_document_id"]
                ),
                "expected_asset_id": result["expected_asset_id"],
                "returned_document_id": first_run[
                    "top_document_id"
                ],
                "returned_asset_id": first_run[
                    "top_asset_id"
                ],
                "returned_document_type": first_run[
                    "top_document_type"
                ],
                "returned_status": first_run["top_status"],
                "detected_intent": first_run[
                    "detected_intent"
                ],
                "successful_runs": successful_runs,
                "total_runs": RUNS_PER_QUERY,
            })

    return {
        "query_count": len(results),
        "runs_per_query": RUNS_PER_QUERY,
        "total_measured_runs": len(all_runs),
        "top_1_retrieval_accuracy": round(
            top_1_accuracy,
            4,
        ),
        "failed_query_count": len(failed_queries),
        "failed_queries": failed_queries,
        "latency_ms": latency_metrics,
        "sub_second_p95_requirement": {
            "requirement_ms": 1000,
            "actual_p95_ms": p95_total,
            "passed": p95_total < 1000,
        },
    }


def write_output(results, metrics):
    """Writes reproducible benchmark results."""
    output = {
        "benchmark": (
            "AEGIS Lakehouse FAST Hybrid Retrieval"
        ),
        "generated_at": now_utc(),
        "corpus": {
            "collection_name": (
                lakehouse_search.COLLECTION_NAME
            ),
            "gold_chunks_file": str(
                lakehouse_search.GOLD_CHUNKS_FILE
            ),
            "expected_chunks": 1000,
        },
        "retrieval_mode": {
            "includes": [
                "Ollama query embedding",
                "Qdrant vector search",
                "BM25 keyword search",
                "Reciprocal Rank Fusion",
                "Schema-aware metadata reranking",
            ],
            "schema_reranking": {
                "signals": [
                    "asset_id exact match",
                    "query intent",
                    "document_type",
                    "document status",
                    "service bulletin authority for current configuration",
                ],
                "local_only": True,
            },
            "excludes": [
                "cross-encoder reranking",
                "LLM answer generation",
                "NLI citation validation",
            ],
        },
        "metrics": metrics,
        "results": results,
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )


def main():
    print("=" * 70)
    print("AEGIS LAKEHOUSE FAST RETRIEVAL BENCHMARK")
    print("=" * 70)
    print(
        "Mode: Vector Search + BM25 + RRF + "
        "Schema-Aware Reranking (no LLM)"
    )
    print(
        f"Queries: {len(QUERIES)} | "
        f"Runs per query: {RUNS_PER_QUERY}"
    )

    print()
    print("Loading Gold chunks and creating BM25 index...")

    chunks, _, bm25 = lakehouse_search.load_search_index()

    print(f"Loaded chunks: {len(chunks)}")

    if len(chunks) != 1000:
        print(
            "WARNING: expected 1000 chunks, "
            f"found {len(chunks)}."
        )

    print()
    run_warmup(chunks, bm25)

    results = []

    print()
    print("=" * 70)
    print("MEASUREMENTS")
    print("=" * 70)

    for item in QUERIES:
        print()
        print(f"{item['id']}: {item['query']}")

        result = benchmark_query(
            item=item,
            chunks=chunks,
            bm25=bm25,
        )

        results.append(result)

    metrics = aggregate_metrics(results)

    write_output(
        results=results,
        metrics=metrics,
    )

    latency = metrics["latency_ms"]
    requirement = metrics[
        "sub_second_p95_requirement"
    ]

    print()
    print("=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)
    print(
        f"Measured runs: "
        f"{metrics['total_measured_runs']}"
    )
    print(
        f"Top-1 retrieval accuracy: "
        f"{metrics['top_1_retrieval_accuracy']:.2%}"
    )
    print(
        f"Queries with Top-1 failures: "
        f"{metrics['failed_query_count']}"
    )

    if metrics["failed_queries"]:
        print()
        print("TOP-1 FAILURES")

        for failure in metrics["failed_queries"]:
            print(
                f"  {failure['id']}: "
                f"expected={failure['expected_document_id']} "
                f"| returned={failure['returned_document_id']} "
                f"| type={failure['returned_document_type']} "
                f"| intent={failure['detected_intent']}"
            )

    print()
    print(
        "Query embedding p95: "
        f"{latency['query_embedding_ms']['p95']:.2f} ms"
    )
    print(
        "Vector search p95:    "
        f"{latency['vector_search_ms']['p95']:.2f} ms"
    )
    print(
        "BM25 search p95:      "
        f"{latency['keyword_search_ms']['p95']:.2f} ms"
    )
    print(
        "RRF fusion p95:       "
        f"{latency['rrf_ms']['p95']:.2f} ms"
    )
    print(
        "Schema rerank p95:    "
        f"{latency['schema_rerank_ms']['p95']:.2f} ms"
    )
    print(
        "TOTAL FAST p95:       "
        f"{latency['total_fast_retrieval_ms']['p95']:.2f} ms"
    )

    print()
    print(
        "Sub-second p95 requirement (<1000 ms): "
        f"{'PASS' if requirement['passed'] else 'NOT MET'}"
    )
    print(f"Results: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()