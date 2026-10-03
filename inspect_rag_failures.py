import json


RESULTS_FILE = "rag_evaluation_results.json"


def main():
    with open(
        RESULTS_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        report = json.load(file)

    results = report.get("results", [])

    failures = [
        result
        for result in results
        if (
            result.get("expected_status") == "SUFFICIENT"
            and result.get("grounded") is not True
        )
    ]

    print(f"Groundedness failures: {len(failures)}")

    for result in failures:
        validation = result.get(
            "citation_validation",
            {},
        )

        print()
        print("=" * 70)
        print(f"ID: {result.get('id')}")
        print(f"QUESTION: {result.get('question')}")
        print()
        print("ANSWER:")
        print(result.get("answer") or "<empty>")
        print()
        print(
            "METRICS: "
            f"precision={validation.get('citation_precision')}, "
            f"completeness={validation.get('citation_completeness')}"
        )

        print()
        print("CLAIM → EVIDENCE CHECKS:")

        for check in validation.get("checks", []):
            print()
            print(f"Claim: {check.get('claim')}")
            print(f"Has citation: {check.get('has_citation')}")
            print(f"Supported: {check.get('supported')}")

            for citation in check.get("citations", []):
                print(
                    f"  [{citation.get('citation_id')}] "
                    f"verdict={citation.get('verdict')} "
                    f"score={citation.get('score')} "
                    f"supported={citation.get('supported')}"
                )

                if citation.get("title"):
                    print(
                        f"      title={citation.get('title')}"
                    )

        uncited_claims = validation.get(
            "uncited_claims",
            [],
        )

        if uncited_claims:
            print()
            print("UNCITED CLAIMS:")

            for claim in uncited_claims:
                print(f"- {claim}")


if __name__ == "__main__":
    main()