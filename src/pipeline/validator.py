import re

from src.schema.document import Document


def _score_content(content: str) -> float:
    if not content:
        return 0.0
    alpha_count = len(re.findall(r"[A-Za-z]", content))
    word_count = len(re.findall(r"[A-Za-z]{3,}", content))
    length_score = min(len(content) / 2000, 1.0)
    alpha_score = min(alpha_count / max(len(content), 1) * 2, 1.0)
    word_score = min(word_count / 50, 1.0)
    return round((length_score * 0.35) + (alpha_score * 0.35) + (word_score * 0.30), 3)


def validate_document(document: Document) -> Document:
    log = list(document.cleaning_log)
    if document.extraction_error:
        log.append(f"extraction_error: {document.extraction_error}")
    if not document.content:
        log.append("empty_content")
    if document.content and not document.chunks:
        log.append("no_chunks")

    document.quality_score = _score_content(document.content)
    document.cleaning_log = log
    return document
