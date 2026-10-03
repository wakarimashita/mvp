import json
from datetime import datetime, timezone
from pathlib import Path

import aegis


DATASET = "golden_questions.json"

RESULTS_FILE = "rag_evaluation_results.json"
REPORT_FILE = "rag_evaluation_report.md"


def normalize_text(text):
    """
    Normalizes text for lightweight deterministic answer matching.
    """
    return " ".join(
        str(text or "")
        .lower()
        .replace(".", " ")
        .replace(",", " ")
        .replace(":", " ")
        .replace(";", " ")
        .split()
    )


def answer_contains_expected_value(answer, expected_answer):
    """
    Lightweight answer relevance metric for the current toy benchmark.

    It checks whether the expected answer appears in the generated answer.

    This is intentionally simple and deterministic. For the Azure/Fabric
    version, it can be replaced or supplemented with Foundry evaluation.
    """
    if not expected_answer:
        return None

    normalized_answer = normalize_text(answer)
    normalized_expected = normalize_text(expected_answer)

    return normalized_expected in normalized_answer


def evaluate_sufficient_question(item, run_result):
    """
    Evaluates a question expected to have sufficient evidence.
    """
    answer = run_result.get("answer") or ""
    validation = run_result.get("validation") or {}

    expected_answer = item.get("expected_answer")

    answer_relevant = answer_contains_expected_value(
        answer,
        expected_answer,
    )

    citation_precision = validation.get("citation_precision")
    citation_completeness = validation.get(
        "citation_completeness"
    )

    grounded = validation.get("valid", False)

    return {
        "answer": answer,
        "answer_relevant": answer_relevant,
        "grounded": grounded,
        "citation_precision": citation_precision,
        "citation_completeness": citation_completeness,
        "citation_validation": validation,
    }


def evaluate_insufficient_question(run_result):
    """
    A correct safe refusal is represented by Aegis returning
    status=INSUFFICIENT before LLM generation.
    """
    returned_status = run_result.get("status")

    refusal_correct = returned_status == "INSUFFICIENT"

    return {
        "answer": run_result.get("answer"),
        "answer_relevant": refusal_correct,
        "grounded": refusal_correct,
        "citation_precision": None,
        "citation_completeness": None,
        "citation_validation": run_result.get("validation"),
    }


def evaluate_question(item):
    """
    Runs the existing end-to-end Aegis pipeline for one golden question.
    """
    question = item["question"]
    expected_status = item["expected_status"]

    run_result = aegis.run(question)

    actual_status = run_result.get("status")
    status_correct = actual_status == expected_status

    if expected_status == "SUFFICIENT":
        answer_metrics = evaluate_sufficient_question(
            item,
            run_result,
        )
    else:
        answer_metrics = evaluate_insufficient_question(
            run_result,
        )

    source_ids = []

    for result in run_result.get("results", []):
        result_id = result.get("id")

        if result_id:
            source_ids.append(result_id)

    expected_source = item.get("expected_source")

    if expected_source:
        source_correct = expected_source in source_ids
    else:
        source_correct = True

    return {
        "id": item["id"],
        "question": question,

        "expected_status": expected_status,
        "actual_status": actual_status,
        "status_correct": status_correct,

        "expected_answer": item.get("expected_answer"),
        "expected_source": expected_source,
        "retrieved_source_ids": source_ids,
        "source_correct": source_correct,

        **answer_metrics,
    }


def percentage(numerator, denominator):
    if denominator == 0:
        return 0.0

    return round(numerator / denominator, 4)


def average(values):
    values = [
        value
        for value in values
        if value is not None
    ]

    if not values:
        return None

    return round(sum(values) / len(values), 4)


def build_metrics(results):
    """
    Aggregates benchmark metrics.
    """
    total = len(results)

    sufficient_results = [
        result
        for result in results
        if result["expected_status"] == "SUFFICIENT"
    ]

    insufficient_results = [
        result
        for result in results
        if result["expected_status"] == "INSUFFICIENT"
    ]

    return {
        "total_questions": total,
        "sufficient_questions": len(sufficient_results),
        "insufficient_questions": len(insufficient_results),

        "status_accuracy": percentage(
            sum(
                result["status_correct"]
                for result in results
            ),
            total,
        ),

        "source_retrieval_accuracy": percentage(
            sum(
                result["source_correct"]
                for result in sufficient_results
            ),
            len(sufficient_results),
        ),

        "answer_relevance": percentage(
            sum(
                result["answer_relevant"] is True
                for result in sufficient_results
            ),
            len(sufficient_results),
        ),

        "groundedness": percentage(
            sum(
                result["grounded"] is True
                for result in sufficient_results
            ),
            len(sufficient_results),
        ),

        "safe_refusal_accuracy": percentage(
            sum(
                result["status_correct"]
                for result in insufficient_results
            ),
            len(insufficient_results),
        ),

        "citation_precision": average([
            result["citation_precision"]
            for result in sufficient_results
        ]),

        "citation_completeness": average([
            result["citation_completeness"]
            for result in sufficient_results
        ]),
    }


def build_failures(results):
    """
    Creates a concrete failure analysis for the Markdown report.
    """
    failures = []

    for result in results:
        reasons = []

        if not result["status_correct"]:
            reasons.append(
                "Status mismatch: "
                f"expected={result['expected_status']}, "
                f"actual={result['actual_status']}"
            )

        if not result["source_correct"]:
            reasons.append(
                "Expected source was not retrieved: "
                f"{result['expected_source']}"
            )

        if (
            result["expected_status"] == "SUFFICIENT"
            and result["answer_relevant"] is not True
        ):
            reasons.append(
                "Generated answer does not contain the expected benchmark answer."
            )

        if (
            result["expected_status"] == "SUFFICIENT"
            and result["grounded"] is not True
        ):
            reasons.append(
                "Citation validation failed: answer is not fully grounded."
            )

        if reasons:
            failures.append({
                "id": result["id"],
                "question": result["question"],
                "answer": result["answer"],
                "reasons": reasons,
                "citation_validation": result[
                    "citation_validation"
                ],
            })

    return failures


def metric_percent(value):
    if value is None:
        return "N/A"

    return f"{value:.2%}"


def build_markdown_report(metrics, results, failures):
    """
    Builds the required human-readable evaluation report.
    """
    generated_at = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "# AEGIS — End-to-End RAG Evaluation Report",
        "",
        f"Generated: `{generated_at}`",
        "",
        "## Benchmark Scope",
        "",
        "- Benchmark: `golden_questions.json`",
        f"- Total questions: **{metrics['total_questions']}**",
        (
            f"- Questions with sufficient evidence: "
            f"**{metrics['sufficient_questions']}**"
        ),
        (
            f"- Questions requiring refusal: "
            f"**{metrics['insufficient_questions']}**"
        ),
        "",
        "## Metrics",
        "",
        (
            f"- Status accuracy: "
            f"**{metric_percent(metrics['status_accuracy'])}**"
        ),
        (
            f"- Source retrieval accuracy: "
            f"**{metric_percent(metrics['source_retrieval_accuracy'])}**"
        ),
        (
            f"- Answer relevance: "
            f"**{metric_percent(metrics['answer_relevance'])}**"
        ),
        (
            f"- Groundedness: "
            f"**{metric_percent(metrics['groundedness'])}**"
        ),
        (
            f"- Citation Precision: "
            f"**{metric_percent(metrics['citation_precision'])}**"
        ),
        (
            f"- Citation Completeness: "
            f"**{metric_percent(metrics['citation_completeness'])}**"
        ),
        (
            f"- Safe refusal accuracy: "
            f"**{metric_percent(metrics['safe_refusal_accuracy'])}**"
        ),
        "",
        "## Metric Definitions",
        "",
        "- **Status accuracy:** Knowledge Guard returns the expected `SUFFICIENT` or `INSUFFICIENT` status.",
        "- **Source retrieval accuracy:** expected source appears in retrieved evidence for answerable questions.",
        "- **Answer relevance:** generated answer contains the expected answer from the toy benchmark.",
        "- **Groundedness:** strict Citation Validator accepts every generated factual claim.",
        "- **Citation Precision:** fraction of claim-to-citation pairs semantically supported by evidence.",
        "- **Citation Completeness:** fraction of factual claims carrying at least one citation.",
        "- **Safe refusal accuracy:** questions without sufficient knowledge are refused before LLM answer generation.",
        "",
        "## Failure Analysis",
        "",
    ]

    if not failures:
        lines.append(
            "No failures detected in this benchmark run."
        )
    else:
        for failure in failures:
            lines.extend([
                f"### {failure['id']}",
                "",
                f"**Question:** {failure['question']}",
                "",
                "**Failure reasons:**",
            ])

            for reason in failure["reasons"]:
                lines.append(f"- {reason}")

            if failure["answer"]:
                lines.extend([
                    "",
                    "**Generated answer:**",
                    "",
                    "```text",
                    failure["answer"],
                    "```",
                ])

            validation = failure.get("citation_validation") or {}

            if validation:
                lines.extend([
                    "",
                    f"**Citation Precision:** "
                    f"{validation.get('citation_precision', 'N/A')}",
                    "",
                    f"**Citation Completeness:** "
                    f"{validation.get('citation_completeness', 'N/A')}",
                ])

            lines.append("")

    lines.extend([
        "## Per-Question Results",
        "",
        "| ID | Expected status | Actual status | Status | Source | Relevance | Grounded | Citation Precision | Citation Completeness |",
        "|---|---|---|---|---|---|---|---:|---:|",
    ])

    for result in results:
        precision = result["citation_precision"]
        completeness = result["citation_completeness"]

        lines.append(
            f"| {result['id']} | "
            f"{result['expected_status']} | "
            f"{result['actual_status']} | "
            f"{result['status_correct']} | "
            f"{result['source_correct']} | "
            f"{result['answer_relevant']} | "
            f"{result['grounded']} | "
            f"{precision if precision is not None else 'N/A'} | "
            f"{completeness if completeness is not None else 'N/A'} |"
        )

    lines.extend([
        "",
        "## Current Benchmark Limitation",
        "",
        "This is a local toy benchmark over two documents. It validates the Aegis pipeline mechanics, but it does not yet represent production diversity of document types, assets, permissions, or multi-hop Graph RAG questions.",
        "",
    ])

    return "\n".join(lines)


def main():
    dataset_path = Path(DATASET)

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path.resolve()}"
        )

    with open(
        dataset_path,
        "r",
        encoding="utf-8",
    ) as file:
        dataset = json.load(file)

    results = []

    for item in dataset:
        print()
        print("=" * 70)
        print(
            f"EVALUATING {item['id']}: "
            f"{item['question']}"
        )
        print("=" * 70)

        result = evaluate_question(item)
        results.append(result)

        print()
        print("EVALUATION RESULT")
        print(f"Status correct: {result['status_correct']}")
        print(f"Source correct: {result['source_correct']}")
        print(
            f"Answer relevant: "
            f"{result['answer_relevant']}"
        )
        print(f"Grounded: {result['grounded']}")

        if result["citation_precision"] is not None:
            print(
                "Citation Precision: "
                f"{result['citation_precision']:.2%}"
            )

        if result["citation_completeness"] is not None:
            print(
                "Citation Completeness: "
                f"{result['citation_completeness']:.2%}"
            )

    metrics = build_metrics(results)
    failures = build_failures(results)

    output = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "dataset": DATASET,
        "metrics": metrics,
        "failures": failures,
        "results": results,
    }

    with open(
        RESULTS_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    report = build_markdown_report(
        metrics,
        results,
        failures,
    )

    with open(
        REPORT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        file.write(report)

    print()
    print("=" * 70)
    print("AEGIS END-TO-END EVALUATION COMPLETE")
    print("=" * 70)
    print(
        f"Status accuracy: "
        f"{metric_percent(metrics['status_accuracy'])}"
    )
    print(
        f"Source retrieval accuracy: "
        f"{metric_percent(metrics['source_retrieval_accuracy'])}"
    )
    print(
        f"Answer relevance: "
        f"{metric_percent(metrics['answer_relevance'])}"
    )
    print(
        f"Groundedness: "
        f"{metric_percent(metrics['groundedness'])}"
    )
    print(
        f"Citation Precision: "
        f"{metric_percent(metrics['citation_precision'])}"
    )
    print(
        f"Citation Completeness: "
        f"{metric_percent(metrics['citation_completeness'])}"
    )
    print(
        f"Safe refusal accuracy: "
        f"{metric_percent(metrics['safe_refusal_accuracy'])}"
    )
    print(f"JSON results: {RESULTS_FILE}")
    print(f"Markdown report: {REPORT_FILE}")


if __name__ == "__main__":
    main()