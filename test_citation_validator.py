from citation import build_citations
from citation_validator import validate_citations


def make_citations():
    evidence = [
        {
            "id": "SB-104",
            "title": "Service Bulletin SB-104",
            "source": "service_bulletin_sb104.json",
            "page": 1,
            "section": "Sensor replacement",
            "version": "1.0",
            "status": "current",
            "text": (
                "For pump P-481, pressure sensor E17 was replaced "
                "with pressure sensor E21. "
                "This bulletin supersedes the previous manual."
            ),
        },
        {
            "id": "P481-MANUAL-V1",
            "title": "Pump P-481 Manual",
            "source": "pump_p481_manual_v1.json",
            "page": 12,
            "section": "Pressure sensor",
            "version": "1.0",
            "status": "superseded",
            "text": "Pump P-481 uses pressure sensor E17.",
        },
    ]

    return build_citations(evidence)


def test_correct_complete_citation():
    citations = make_citations()

    answer = "P-481 currently uses pressure sensor E21. [C1]"

    result = validate_citations(answer, citations)

    assert result["valid"] is True
    assert result["valid_ids"] is True
    assert result["citation_precision"] == 1.0
    assert result["claim_support_rate"] == 1.0

    # Поле появится после обновления citation_validator.py
    if "citation_completeness" in result:
        assert result["citation_completeness"] == 1.0

    print("PASS: correct citation")


def test_superseded_source_is_rejected():
    citations = make_citations()

    answer = "P-481 currently uses pressure sensor E21. [C2]"

    result = validate_citations(answer, citations)

    assert result["valid"] is False
    assert result["citation_precision"] == 0.0
    assert result["claim_support_rate"] == 0.0

    verdict = result["checks"][0]["citations"][0]["verdict"]
    assert verdict in ("contradiction", "neutral")

    print("PASS: superseded source rejected")


def test_invalid_citation_id_is_rejected():
    citations = make_citations()

    answer = "P-481 currently uses pressure sensor E21. [C99]"

    result = validate_citations(answer, citations)

    assert result["valid"] is False
    assert result["valid_ids"] is False
    assert result["invalid_ids"] == ["C99"]
    assert result["citation_precision"] == 0.0

    print("PASS: invalid citation ID rejected")


def test_mixed_citations_are_rejected_by_strict_policy():
    citations = make_citations()

    # C1 подтверждает E21, C2 — старый источник про E17.
    answer = "P-481 currently uses pressure sensor E21. [C1][C2]"

    result = validate_citations(answer, citations)

    assert result["citation_precision"] == 0.5
    assert result["claim_support_rate"] == 1.0

    # При строгом Citation Precision лишняя неподтверждающая
    # ссылка делает ответ невалидным.
    assert result["valid"] is False

    print("PASS: mixed citations rejected by strict precision policy")


if __name__ == "__main__":
    test_correct_complete_citation()
    test_superseded_source_is_rejected()
    test_invalid_citation_id_is_rejected()
    test_mixed_citations_are_rejected_by_strict_policy()

    print("\nAll Citation Precision tests passed.")