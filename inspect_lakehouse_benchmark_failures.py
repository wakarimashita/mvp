import json
from pathlib import Path


BENCHMARK_FILE = Path(
    "local_lakehouse/gold/fast_retrieval_benchmark.json"
)


def main():
    if not BENCHMARK_FILE.exists():
        raise FileNotFoundError(
            f"Benchmark file not found: "
            f"{BENCHMARK_FILE.resolve()}"
        )

    with open(
        BENCHMARK_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        benchmark = json.load(file)

    failures = []

    for result in benchmark.get("results", []):
        failed_runs = [
            run
            for run in result.get("runs", [])
            if not run.get("top_result_correct")
        ]

        if failed_runs:
            failures.append({
                "id": result.get("id"),
                "query": result.get("query"),
                "expected_asset_id": result.get(
                    "expected_asset_id"
                ),
                "expected_document_id": result.get(
                    "expected_document_id"
                ),
                "failed_runs": failed_runs,
            })

    print(
        f"Queries with top-1 failures: "
        f"{len(failures)}"
    )

    for failure in failures:
        print()
        print("=" * 70)
        print(failure["id"])
        print(f"Query: {failure['query']}")
        print(
            "Expected: "
            f"{failure['expected_document_id']} "
            f"(asset {failure['expected_asset_id']})"
        )

        for run in failure["failed_runs"]:
            print()
            print(
                f"  Run {run['run']}: "
                f"returned {run['top_document_id']} "
                f"(asset {run['top_asset_id']})"
            )
            print(
                f"  Title: {run['top_title']}"
            )
            print(
                "  Total FAST latency: "
                f"{run['timings_ms']['total_fast_retrieval_ms']:.2f} ms"
            )


if __name__ == "__main__":
    main()