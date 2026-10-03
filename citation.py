def get_value(item, field, default=None):
    """
    Получает значение сначала из самого item,
    затем из item["metadata"].

    Поддерживает:
    - flat result;
    - result с вложенным metadata.
    """
    if item.get(field) is not None:
        return item.get(field)

    metadata = item.get("metadata", {})

    if isinstance(metadata, dict):
        return metadata.get(field, default)

    return default


def build_validation_evidence_text(item):
    """
    Формирует внутренний evidence text для Citation Validator.

    Включает:
    - фактический текст chunk/document;
    - provenance metadata.

    Это важно: metadata является evidence для вопросов о:
    - title;
    - version;
    - status;
    - effective date;
    - asset;
    - source;
    - page;
    - section;
    - supersedes relationship.

    Этот текст НЕ показывается пользователю в списке citations.
    """
    metadata = item.get("metadata", {})

    if not isinstance(metadata, dict):
        metadata = {}

    document_text = (
        item.get("text")
        or item.get("content")
        or item.get("chunk_text")
        or metadata.get("text")
        or metadata.get("content")
        or ""
    )

    document_id = (
        get_value(item, "id")
        or get_value(item, "document_id")
        or get_value(item, "doc_id")
    )

    title = get_value(item, "title")
    version = get_value(item, "version")
    status = get_value(item, "status")
    effective_date = get_value(item, "effective_date")
    asset_id = get_value(item, "asset_id")
    supersedes = get_value(item, "supersedes")
    source = get_value(item, "source")
    page = get_value(item, "page")
    section = get_value(item, "section")
    document_type = get_value(item, "document_type")

    metadata_facts = []

    if document_id:
        metadata_facts.append(
            f"Document ID is {document_id}."
        )

    if title:
        metadata_facts.append(
            f"Document title is {title}."
        )

    if document_type:
        metadata_facts.append(
            f"Document type is {document_type}."
        )

    if version:
        metadata_facts.append(
            f"Document version is {version}."
        )

    if status:
        metadata_facts.append(
            f"Document status is {status}."
        )

    if effective_date:
        metadata_facts.append(
            f"Document effective date is {effective_date}."
        )

    if asset_id:
        metadata_facts.append(
            f"Document applies to asset {asset_id}."
        )

    if supersedes:
        metadata_facts.append(
            f"Document supersedes document {supersedes}."
        )

    if source:
        metadata_facts.append(
            f"Document source is {source}."
        )

    if page is not None:
        metadata_facts.append(
            f"Relevant document page is {page}."
        )

    if section:
        metadata_facts.append(
            f"Relevant document section is {section}."
        )

    parts = [str(document_text).strip()]

    parts.extend(metadata_facts)

    return "\n".join(
        part
        for part in parts
        if part
    )


def build_citations(evidence_items):
    """
    Создаёт citations для:
    - LLM prompt;
    - UI;
    - Citation Validator.

    evidence_text используется только внутри Citation Validator.
    """
    citations = []

    for index, item in enumerate(evidence_items, start=1):
        document_id = (
            get_value(item, "id")
            or get_value(item, "document_id")
            or get_value(item, "doc_id")
            or get_value(item, "source")
        )

        citations.append({
            "id": f"C{index}",
            "document_id": document_id,
            "title": get_value(
                item,
                "title",
                "Untitled document",
            ),
            "source": get_value(item, "source"),
            "page": get_value(item, "page"),
            "section": get_value(item, "section"),
            "version": get_value(item, "version"),
            "status": get_value(item, "status"),
            "effective_date": get_value(
                item,
                "effective_date",
            ),
            "supersedes": get_value(item, "supersedes"),

            # Only for internal claim -> evidence validation.
            "evidence_text": build_validation_evidence_text(
                item
            ),
        })

    return citations


def format_citations(citations):
    """
    Формирует список источников для показа пользователю.

    evidence_text намеренно не отображается.
    """
    lines = []

    for citation in citations:
        location = []

        if citation.get("page") is not None:
            location.append(
                f"page {citation['page']}"
            )

        if citation.get("section"):
            location.append(
                str(citation["section"])
            )

        line = (
            f"[{citation['id']}] "
            f"{citation['title']}"
        )

        if citation.get("version"):
            line += f" v{citation['version']}"

        if citation.get("status"):
            line += f" [{citation['status']}]"

        if location:
            line += f" — {', '.join(location)}"

        if citation.get("source"):
            line += f" ({citation['source']})"

        lines.append(line)

    return "\n".join(lines)