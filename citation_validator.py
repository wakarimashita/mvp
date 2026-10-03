import re
from functools import lru_cache

from transformers import pipeline


CITATION_PATTERN = re.compile(r"\[(C\d+)\]")

# Предложение с необязательным хвостом citations:
# "P-481 uses E21. [C1][C2]"
SENTENCE_WITH_CITATIONS_PATTERN = re.compile(
    r"(?P<sentence>[^.!?\n]+[.!?])"
    r"(?P<citations>\s*(?:\[(?:C\d+)\]\s*)*)"
)

NON_FACTUAL_PREFIXES = (
    "источники",
    "источник",
    "sources",
    "source",
    "references",
    "reference",
    "примечание",
    "note",
)

# Такие фразы допустимы без citations: это безопасный отказ,
# а не утверждение, основанное на knowledge base.
REFUSAL_PREFIXES = (
    "недостаточно данных",
    "недостаточно evidence",
    "не могу подтвердить",
    "не могу дать",
    "невозможно подтвердить",
    "отсутствуют подтверждающие",
    "недостаточно информации",
    "i don't have enough evidence",
    "insufficient evidence",
    "i cannot confirm",
    "cannot confirm",
)


@lru_cache(maxsize=1)
def get_nli_model():
    """
    Multilingual NLI-модель для проверки:
    evidence -> подтверждает ли evidence claim.
    """
    model_name = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"

    return pipeline(
        task="text-classification",
        model=model_name,
        tokenizer=model_name,
        top_k=None,
        truncation=True,
        max_length=512,
    )


def normalize_text(text):
    """Приводит текст к одной строке без лишних пробелов."""
    if not text:
        return ""

    return re.sub(r"\s+", " ", str(text)).strip()


def normalize_label(label):
    """
    Нормализует labels разных версий моделей / transformers.
    """
    label = str(label).strip().lower()

    mapping = {
        "label_0": "entailment",
        "label_1": "neutral",
        "label_2": "contradiction",
    }

    return mapping.get(label, label)


def is_non_factual_or_refusal(claim):
    """
    True, если строка не требует citation:
    - заголовок Sources / Источники;
    - безопасный отказ при отсутствии evidence;
    - слишком короткая техническая строка.
    """
    claim = normalize_text(claim)

    if not claim:
        return True

    claim_lower = claim.lower().strip(" -—–:;")

    if claim_lower.startswith(NON_FACTUAL_PREFIXES):
        return True

    if claim_lower.startswith(REFUSAL_PREFIXES):
        return True

    # Например: "---", "1.", "Шаг 1:"
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", claim)

    if len(letters) < 3:
        return True

    return False


def prepare_answer(answer):
    """
    Поддерживает оба формата:

    P-481 uses E21. [C1]

    и:

    P-481 uses E21.
    [C1]
    """
    answer = str(answer or "")
    answer = answer.replace("\r\n", "\n").replace("\r", "\n")

    # Citation, стоящий отдельно на следующей строке,
    # присоединяем к предыдущему предложению.
    answer = re.sub(
        r"([.!?])\s*\n\s*((?:\[(?:C\d+)\]\s*)+)",
        r"\1 \2",
        answer,
    )

    return answer


def extract_claims(answer):
    """
    Извлекает atomic claims и citations.

    Поддерживает:

    1. Citation перед точкой:
       Pump P-481 uses E21 [C1].

    2. Citation после точки:
       Pump P-481 uses E21. [C1]

    3. Несколько atomic claims в одном предложении:
       SB-104 states E21 [C1], while the old manual states E17 [C2].

    4. Несколько citations для одного claim:
       Pump P-481 uses E21 [C1][C2].

    5. Версии и десятичные числа:
       SB-104 v1.0 is current [C1].
    """
    answer = prepare_answer(answer)

    # Переносим citations после точки до точки:
    #
    # "Pump uses E21. [C1]"
    # ->
    # "Pump uses E21 [C1]."
    #
    # Это позволяет одинаково обработать оба допустимых стиля.
    answer = re.sub(
        r"([.!?])\s*((?:\[(?:C\d+)\]\s*)+)",
        r" \2\1",
        answer,
    )

    # Защита десятичных чисел и версий:
    # "v1.0" не должно стать двумя предложениями.
    protected_answer = re.sub(
        r"(?<=\d)\.(?=\d)",
        "<DECIMAL_DOT>",
        answer,
    )

    sentences = re.findall(
        r"[^.!?\n]+(?:[.!?]+|$)",
        protected_answer,
    )

    claims = []

    for sentence in sentences:
        sentence = sentence.replace("<DECIMAL_DOT>", ".")
        sentence = normalize_text(sentence)

        if not sentence:
            continue

        citation_matches = list(
            CITATION_PATTERN.finditer(sentence)
        )

        # Нет citations: это потенциальный uncited claim.
        if not citation_matches:
            claim = sentence.strip(" -—–:;")

            if not is_non_factual_or_refusal(claim):
                claims.append({
                    "claim": claim,
                    "citation_ids": [],
                })

            continue

        previous_end = 0
        pending_claim_index = None

        for index, match in enumerate(citation_matches):
            citation_id = match.group(1)

            # Текст между окончанием предыдущей citation
            # и началом текущей citation относится к current claim.
            claim_part = sentence[previous_end:match.start()]

            # После предыдущего claim LLM часто пишет:
            # ", while ...", "; however ...", "and ...".
            # Это не должно входить в semantic claim.
            claim_part = re.sub(
                r"^\s*[,;:.-]?\s*"
                r"(while|whereas|but|however|and)\s+",
                "",
                claim_part,
                flags=re.IGNORECASE,
            )

            claim_part = normalize_text(claim_part)
            claim_part = claim_part.strip(" -—–:;,")

            # Если перед citation есть содержательный текст,
            # создаём новый atomic claim.
            if claim_part:
                # Убираем финальные punctuation, чтобы NLI не получал
                # лишний символ после normalisation.
                claim_part = claim_part.rstrip(".!?")

                if not is_non_factual_or_refusal(claim_part):
                    claims.append({
                        "claim": claim_part,
                        "citation_ids": [citation_id],
                    })

                    pending_claim_index = len(claims) - 1

            # Если между citations текста нет:
            #
            # "Pump uses E21 [C1][C2]."
            #
            # значит C2 — дополнительная citation к предыдущему claim.
            elif pending_claim_index is not None:
                existing_ids = set(
                    claims[pending_claim_index]["citation_ids"]
                )
                existing_ids.add(citation_id)

                claims[pending_claim_index]["citation_ids"] = sorted(
                    existing_ids
                )

            previous_end = match.end()

        # Если после последней citation остался meaningful text,
        # он является uncited claim.
        tail = sentence[previous_end:]
        tail = normalize_text(tail).strip(" -—–:;,")

        if tail and not is_non_factual_or_refusal(tail):
            claims.append({
                "claim": tail,
                "citation_ids": [],
            })

    return claims


def evaluate_claim_against_evidence(claim, evidence_text):
    """
    Выполняет semantic validation пары claim -> evidence.
    """
    claim = normalize_text(claim)
    evidence_text = normalize_text(evidence_text)

    if not evidence_text:
        return {
            "verdict": "missing_evidence",
            "score": 0.0,
            "supported": False,
            "label_scores": {},
        }

    classifier = get_nli_model()

    # premise = evidence
    # hypothesis = claim
    result = classifier({
        "text": evidence_text,
        "text_pair": claim,
    })

    if result and isinstance(result[0], list):
        result = result[0]

    label_scores = {
        normalize_label(item["label"]): float(item["score"])
        for item in result
    }

    entailment_score = label_scores.get("entailment", 0.0)
    neutral_score = label_scores.get("neutral", 0.0)
    contradiction_score = label_scores.get("contradiction", 0.0)

    if contradiction_score >= 0.50:
        return {
            "verdict": "contradiction",
            "score": round(contradiction_score, 4),
            "supported": False,
            "label_scores": label_scores,
        }

    if entailment_score >= 0.50:
        return {
            "verdict": "entailment",
            "score": round(entailment_score, 4),
            "supported": True,
            "label_scores": label_scores,
        }

    return {
        "verdict": "neutral",
        "score": round(neutral_score, 4),
        "supported": False,
        "label_scores": label_scores,
    }


def validate_citations(
    answer,
    citations,
    min_citation_precision=1.0,
    require_complete_citations=True,
):
    """
    Проверяет claim -> evidence и полноту citations.

    Метрики:

    citation_precision:
        Подтверждённые пары claim-citation / все пары claim-citation.

    claim_support_rate:
        Claims с хотя бы одним подтверждающим evidence /
        все claims с citations.

    citation_completeness:
        Claims с хотя бы одной citation / все factual claims.

    По умолчанию policy строгая:
    - Citation Precision должен быть 1.0;
    - у каждого factual claim должна быть citation;
    - все cited claims должны быть evidence-supported.
    """
    citation_map = {
        citation["id"]: citation
        for citation in citations
        if citation.get("id")
    }

    used_ids = set(CITATION_PATTERN.findall(answer))
    valid_ids = set(citation_map.keys())
    invalid_ids = sorted(used_ids - valid_ids)

    extracted_claims = extract_claims(answer)

    checks = []
    unsupported_claims = []
    uncited_claims = []

    total_citation_pairs = 0
    supported_citation_pairs = 0
    supported_claims = 0
    cited_claims = 0

    for extracted_claim in extracted_claims:
        claim = extracted_claim["claim"]
        citation_ids = extracted_claim["citation_ids"]

        if not citation_ids:
            uncited_claims.append(claim)

            checks.append({
                "claim": claim,
                "has_citation": False,
                "supported": False,
                "citations": [],
            })
            continue

        cited_claims += 1
        claim_is_supported = False
        citation_checks = []

        for citation_id in citation_ids:
            total_citation_pairs += 1

            citation = citation_map.get(citation_id)

            if citation is None:
                citation_check = {
                    "citation_id": citation_id,
                    "verdict": "invalid_citation_id",
                    "score": 0.0,
                    "supported": False,
                    "label_scores": {},
                }
            else:
                validation = evaluate_claim_against_evidence(
                    claim=claim,
                    evidence_text=citation.get("evidence_text", ""),
                )

                citation_check = {
                    "citation_id": citation_id,
                    "document_id": citation.get("document_id"),
                    "title": citation.get("title"),
                    "source": citation.get("source"),
                    "page": citation.get("page"),
                    "section": citation.get("section"),
                    "status": citation.get("status"),
                    **validation,
                }

            if citation_check["supported"]:
                supported_citation_pairs += 1
                claim_is_supported = True

            citation_checks.append(citation_check)

        if claim_is_supported:
            supported_claims += 1
        else:
            unsupported_claims.append(claim)

        checks.append({
            "claim": claim,
            "has_citation": True,
            "supported": claim_is_supported,
            "citations": citation_checks,
        })

    citation_precision = (
        supported_citation_pairs / total_citation_pairs
        if total_citation_pairs
        else 0.0
    )

    claim_support_rate = (
        supported_claims / cited_claims
        if cited_claims
        else 0.0
    )

    citation_completeness = (
        cited_claims / len(extracted_claims)
        if extracted_claims
        else 1.0
    )

    valid_ids_result = len(invalid_ids) == 0
    precision_passed = citation_precision >= min_citation_precision
    support_passed = (
        cited_claims > 0
        and claim_support_rate == 1.0
    )

    completeness_passed = (
        citation_completeness == 1.0
        if require_complete_citations
        else True
    )

    valid = (
        valid_ids_result
        and precision_passed
        and support_passed
        and completeness_passed
    )

    return {
        "valid": valid,

        "valid_ids": valid_ids_result,
        "used_ids": sorted(used_ids),
        "invalid_ids": invalid_ids,

        "citation_precision": round(citation_precision, 3),
        "supported_citation_pairs": supported_citation_pairs,
        "total_citation_pairs": total_citation_pairs,
        "min_citation_precision": min_citation_precision,
        "precision_passed": precision_passed,

        "claim_support_rate": round(claim_support_rate, 3),
        "supported_claims": supported_claims,
        "total_cited_claims": cited_claims,
        "unsupported_claims": unsupported_claims,

        "citation_completeness": round(citation_completeness, 3),
        "total_factual_claims": len(extracted_claims),
        "cited_claims": cited_claims,
        "uncited_claims": uncited_claims,
        "completeness_passed": completeness_passed,

        "checks": checks,
    }