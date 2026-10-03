import re


MIN_RERANKER_SCORE = 0.20
MIN_TERM_COVERAGE = 0.50


STOP_WORDS = {
    # English question words and common grammar
    "what",
    "which",
    "who",
    "when",
    "where",
    "why",
    "how",
    "does",
    "did",
    "do",
    "is",
    "are",
    "was",
    "were",
    "the",
    "a",
    "an",
    "of",
    "for",
    "to",
    "in",
    "on",
    "at",
    "with",
    "and",
    "or",
    "that",
    "this",
    "these",
    "those",
    "it",
    "its",
    "be",
    "been",
    "by",
    "from",
    "between",

    # Generic domain terms.
    # They do not prove that the requested fact exists.
    "pump",
    "document",
    "documents",
    "service",
    "bulletin",
    "manual",
    "asset",
    "version",
    "old",
    "new",
}


CAUSAL_TERMS = {
    "because",
    "reason",
    "reasons",
    "caused",
    "cause",
    "due",
    "therefore",
    "result",
    "results",
    "resulted",
    "root",
    "failure",
    "failed",
    "maintenance",
    "repair",
    "damaged",
    "damage",
    "fault",
    "faulty",
}


def normalize_text(text):
    """
    Converts input to lowercase text with normalized whitespace.
    """
    return re.sub(
        r"\s+",
        " ",
        str(text or "").lower(),
    ).strip()


def tokenize(text):
    """
    Extracts tokens while preserving IDs such as:
    - P-481
    - E17
    - E21
    - SB-104
    - 2026-09-01
    """
    return re.findall(
        r"[a-z0-9]+(?:-[a-z0-9]+)*",
        normalize_text(text),
    )


def extract_asset_ids(text):
    """
    Temporary local asset-ID extractor.

    This is intentionally isolated in one function so it can later be
    replaced by schema-driven entity extraction during Azure/Fabric migration.
    """
    return {
        asset.upper()
        for asset in re.findall(
            r"\bP-\d+\b",
            str(text or ""),
            flags=re.IGNORECASE,
        )
    }


def get_result_metadata(result):
    """
    Supports both nested metadata and flat result formats.
    """
    metadata = result.get("metadata", {})

    if not isinstance(metadata, dict):
        return {}

    return metadata


def get_result_id(result):
    """
    Gets a document ID from either a flat result or nested metadata.
    """
    metadata = get_result_metadata(result)

    return (
        result.get("id")
        or metadata.get("id")
        or metadata.get("document_id")
    )


def get_metadata_value(result, field):
    """
    Gets a metadata field from nested metadata first, then flat result.
    """
    metadata = get_result_metadata(result)

    if metadata.get(field) is not None:
        return metadata.get(field)

    return result.get(field)


def build_evidence_text(result):
    """
    Builds one searchable evidence string from content and metadata.

    Metadata is valid evidence for questions about:
    - status;
    - effective date;
    - section;
    - source;
    - supersedes relationship;
    - document title and version.
    """
    metadata = get_result_metadata(result)

    parts = [
        result.get("text", ""),
        result.get("content", ""),
        result.get("chunk_text", ""),
        result.get("title", ""),
        result.get("source", ""),
    ]

    for key, value in metadata.items():
        if value is not None:
            parts.append(f"{key} {value}")

    return normalize_text(
        " ".join(str(part) for part in parts)
    )


def normalize_token_for_match(token):
    """
    Lightweight normalization without external NLP dependencies.

    Examples:
    - supersede -> supersedes
    - specify -> specifies
    - replace -> replaced
    """
    token = token.lower()

    for suffix in ("ing", "ed", "es", "s"):
        if (
            token.endswith(suffix)
            and len(token) > len(suffix) + 3
        ):
            return token[:-len(suffix)]

    return token


def token_matches(query_token, evidence_tokens):
    """
    Checks exact or lightweight stem-like token matching.
    """
    normalized_query = normalize_token_for_match(query_token)

    for evidence_token in evidence_tokens:
        normalized_evidence = normalize_token_for_match(
            evidence_token
        )

        if normalized_query == normalized_evidence:
            return True

        # Prefix matching is allowed only for longer words.
        if len(normalized_query) >= 5:
            if normalized_evidence.startswith(normalized_query):
                return True

            if normalized_query.startswith(normalized_evidence):
                return True

    return False


def extract_meaningful_query_terms(query):
    """
    Extracts query terms for generic evidence coverage validation.

    Asset IDs are excluded because they are validated separately.
    """
    terms = []

    for token in tokenize(query):
        if token in STOP_WORDS:
            continue

        if re.fullmatch(r"p-\d+", token):
            continue

        terms.append(token)

    return sorted(set(terms))


def has_causal_evidence(evidence_text):
    """
    A why-question requires causal explanation, not merely an event.

    Example:
    "E17 was replaced with E21"
    does not answer:
    "Why was E17 replaced?"
    """
    evidence_tokens = set(tokenize(evidence_text))

    return bool(
        evidence_tokens.intersection(CAUSAL_TERMS)
    )


def has_document_title_reference(query, result):
    """
    Checks whether the query references the title of a retrieved document.

    Example:
    Query:
        What is the status of Service Bulletin SB-104?

    Document title:
        Service Bulletin SB-104

    This is generic and does not hardcode document names.
    """
    metadata = get_result_metadata(result)

    title = (
        metadata.get("title")
        or result.get("title")
        or ""
    )

    title_tokens = {
        token
        for token in tokenize(title)
        if token not in STOP_WORDS
    }

    query_tokens = set(tokenize(query))

    if not title_tokens:
        return False

    overlap = title_tokens.intersection(query_tokens)

    # At least half of the meaningful title tokens must be present.
    return len(overlap) / len(title_tokens) >= 0.50


def has_metadata_answerability(query, results):
    """
    Determines whether a query can be answered directly from retrieved
    metadata and document relationships.

    Supported universal categories:

    - document status;
    - effective date;
    - supersedes relationship;
    - current vs superseded change history.

    Returns:
        (True, reason)
    or:
        (False, None)
    """
    query_tokens = set(tokenize(query))

    asks_status = bool(
        query_tokens.intersection(
            {
                "status",
                "current",
                "superseded",
            }
        )
    )

    asks_effective_date = bool(
        query_tokens.intersection(
            {
                "effective",
                "date",
            }
        )
    )

    asks_supersedes = bool(
        query_tokens.intersection(
            {
                "supersede",
                "supersedes",
                "superseded",
            }
        )
    )

    asks_change_history = bool(
        query_tokens.intersection(
            {
                "change",
                "changed",
                "difference",
            }
        )
    )

    result_ids = {
        get_result_id(result)
        for result in results
        if get_result_id(result)
    }

    # Status and effective_date are valid evidence when the query
    # references a retrieved document title.
    for result in results:
        if not has_document_title_reference(query, result):
            continue

        if asks_status and get_metadata_value(result, "status"):
            return (
                True,
                "Document status is available as retrieved metadata.",
            )

        if (
            asks_effective_date
            and get_metadata_value(result, "effective_date")
        ):
            return (
                True,
                "Document effective date is available as retrieved metadata.",
            )

    # Supersedes is valid evidence if a retrieved document explicitly
    # points to another retrieved document.
    if asks_supersedes:
        for result in results:
            supersedes = get_metadata_value(result, "supersedes")

            if supersedes and supersedes in result_ids:
                return (
                    True,
                    "Supersedes relationship is present in retrieved metadata.",
                )

    # Change-history questions need a current document linked to its
    # superseded predecessor, with both documents retrieved.
    if asks_change_history:
        for result in results:
            status = get_metadata_value(result, "status")
            supersedes = get_metadata_value(result, "supersedes")

            if (
                status == "current"
                and supersedes
                and supersedes in result_ids
            ):
                return (
                    True,
                    "Current-to-superseded document relationship is present "
                    "in retrieved metadata.",
                )

    return False, None


def assess_evidence(results, query):
    """
    Deterministic Knowledge Guard.

    Evidence is SUFFICIENT only if one of these paths succeeds:

    1. Metadata / relationship answerability:
       status, effective date, supersedes, change history.

    2. Content answerability:
       - retrieval relevance score is sufficient;
       - requested asset matches retrieved evidence;
       - why-question has causal evidence;
       - retrieved evidence covers enough meaningful query terms.

    This is still a local MVP implementation. Future Azure/Fabric migration
    should replace local asset regex extraction with schema-aware entity
    extraction and retrieval filters.
    """
    if not results:
        return {
            "status": "INSUFFICIENT",
            "reason": "No relevant evidence found.",
        }

    top = results[0]

    reranker_score = float(
        top.get("reranker_score", 0.0)
    )

    top_metadata = get_result_metadata(top)

    query_assets = extract_asset_ids(query)

    result_assets = set()
    all_evidence_text_parts = []

    for result in results:
        metadata = get_result_metadata(result)

        result_asset = (
            metadata.get("asset_id")
            or result.get("asset_id")
        )

        if result_asset:
            result_assets.add(str(result_asset).upper())

        all_evidence_text_parts.append(
            build_evidence_text(result)
        )

    all_evidence_text = normalize_text(
        " ".join(all_evidence_text_parts)
    )

    # Protect against false-positive asset matches:
    # question P-482 must not be answered from evidence about P-481.
    if (
        query_assets
        and not query_assets.intersection(result_assets)
    ):
        return {
            "status": "INSUFFICIENT",
            "reason": (
                "No retrieved evidence matches the requested asset. "
                f"Requested asset(s): {sorted(query_assets)}. "
                f"Retrieved asset(s): "
                f"{sorted(result_assets) or ['none']}."
            ),
            "reranker_score": reranker_score,
            "requested_assets": sorted(query_assets),
            "retrieved_assets": sorted(result_assets),
        }

    # Metadata and graph-like document relations can be sufficient even
    # when text reranking is low. For example, "effective date" might
    # not appear in the document body but exists in document metadata.
    metadata_answerable, metadata_reason = (
        has_metadata_answerability(
            query,
            results,
        )
    )

    if metadata_answerable:
        return {
            "status": "SUFFICIENT",
            "reason": metadata_reason,
            "evidence": results,
            "asset_id": top_metadata.get("asset_id"),
            "reranker_score": reranker_score,
            "requested_assets": sorted(query_assets),
            "retrieved_assets": sorted(result_assets),
            "answerability_type": "metadata_or_relationship",
        }

    # For normal text-content questions, weak reranker relevance means
    # the evidence is not sufficient.
    if reranker_score < MIN_RERANKER_SCORE:
        return {
            "status": "INSUFFICIENT",
            "reason": (
                "Best evidence relevance is too low "
                f"({reranker_score:.4f})."
            ),
            "reranker_score": reranker_score,
            "requested_assets": sorted(query_assets),
            "retrieved_assets": sorted(result_assets),
        }

    # A fact about a replacement does not necessarily explain why the
    # replacement happened.
    if re.search(r"\bwhy\b", normalize_text(query)):
        if not has_causal_evidence(all_evidence_text):
            return {
                "status": "INSUFFICIENT",
                "reason": (
                    "Evidence describes a fact or change, but does not "
                    "contain a causal explanation for the why-question."
                ),
                "reranker_score": reranker_score,
                "requested_assets": sorted(query_assets),
                "retrieved_assets": sorted(result_assets),
            }

    query_terms = extract_meaningful_query_terms(query)
    evidence_tokens = set(tokenize(all_evidence_text))

    matched_terms = [
        term
        for term in query_terms
        if token_matches(term, evidence_tokens)
    ]

    missing_terms = [
        term
        for term in query_terms
        if term not in matched_terms
    ]

    term_coverage = (
        len(matched_terms) / len(query_terms)
        if query_terms
        else 1.0
    )

    if term_coverage < MIN_TERM_COVERAGE:
        return {
            "status": "INSUFFICIENT",
            "reason": (
                "Retrieved evidence does not cover enough of the requested "
                "property or relation. "
                f"Term coverage={term_coverage:.2f}, "
                f"required={MIN_TERM_COVERAGE:.2f}."
            ),
            "reranker_score": reranker_score,
            "matched_terms": matched_terms,
            "missing_terms": missing_terms,
            "term_coverage": round(term_coverage, 3),
            "requested_assets": sorted(query_assets),
            "retrieved_assets": sorted(result_assets),
        }

    return {
        "status": "SUFFICIENT",
        "reason": (
            "Relevant evidence found with matching asset and query terms. "
            f"score={reranker_score:.4f}, "
            f"term_coverage={term_coverage:.2f}."
        ),
        "evidence": results,
        "asset_id": top_metadata.get("asset_id"),
        "reranker_score": reranker_score,
        "matched_terms": matched_terms,
        "missing_terms": missing_terms,
        "term_coverage": round(term_coverage, 3),
        "requested_assets": sorted(query_assets),
        "retrieved_assets": sorted(result_assets),
        "answerability_type": "content",
    }


def print_guard_result(result):
    """
    Prints a readable standalone Guard result.
    """
    print()
    print("=" * 70)
    print("KNOWLEDGE GUARD")
    print("=" * 70)

    print(f"Status: {result['status']}")
    print(f"Reason: {result['reason']}")

    if "answerability_type" in result:
        print(
            "Answerability type: "
            f"{result['answerability_type']}"
        )

    if "term_coverage" in result:
        print(
            "Term coverage: "
            f"{result['term_coverage']}"
        )

    if result.get("missing_terms"):
        print(
            "Missing terms: "
            f"{', '.join(result['missing_terms'])}"
        )


if __name__ == "__main__":
    strong = [
        {
            "id": "doc-sb104",
            "reranker_score": 0.95,
            "text": (
                "Pump P-481 pressure sensor was replaced. "
                "The new pressure sensor is E21."
            ),
            "metadata": {
                "asset_id": "P-481",
                "title": "Service Bulletin SB-104",
                "status": "current",
                "effective_date": "2026-09-01",
                "supersedes": "doc-p481-manual-v2",
            },
        },
        {
            "id": "doc-p481-manual-v2",
            "reranker_score": 0.70,
            "text": "Pump P-481 uses pressure sensor E17.",
            "metadata": {
                "asset_id": "P-481",
                "title": "Pump P-481 Service Manual",
                "status": "superseded",
                "effective_date": "2025-01-01",
            },
        },
    ]

    wrong_asset = [
        {
            "id": "doc-sb104",
            "reranker_score": 0.80,
            "text": "Pump P-481 uses pressure sensor E21.",
            "metadata": {
                "asset_id": "P-481",
                "title": "Service Bulletin SB-104",
                "status": "current",
            },
        }
    ]

    print("CURRENT CONFIGURATION")
    print_guard_result(
        assess_evidence(
            strong,
            "Which pressure sensor does P-481 currently use?",
        )
    )

    print()
    print("DOCUMENT STATUS")
    print_guard_result(
        assess_evidence(
            strong,
            "What is the status of Service Bulletin SB-104?",
        )
    )

    print()
    print("SUPERSEDES RELATIONSHIP")
    print_guard_result(
        assess_evidence(
            strong,
            "Does Service Bulletin SB-104 supersede the P-481 Service Manual?",
        )
    )

    print()
    print("WRONG ASSET")
    print_guard_result(
        assess_evidence(
            wrong_asset,
            "Which pressure sensor does P-482 currently use?",
        )
    )