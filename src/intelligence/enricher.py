import re
from collections import Counter

from src.schema.document import Document


STOPWORDS = {
    "about", "after", "again", "also", "and", "are", "because", "for", "from",
    "have", "into", "notes", "that", "the", "this", "with", "your"
}


def _top_terms(text: str, limit: int = 5) -> list[str]:
    words = [
        word.lower()
        for word in re.findall(r"[A-Za-z]{4,}", text)
        if word.lower() not in STOPWORDS
    ]
    return [word for word, _count in Counter(words).most_common(limit)]


def enrich_document(document: Document) -> Document:
    terms = _top_terms(document.content)
    document.metadata["tags"] = terms
    document.metadata["word_count"] = len(re.findall(r"\S+", document.content))
    document.metadata["chunk_count"] = len(document.chunks)
    if terms:
        document.cleaning_log = [*document.cleaning_log, "enriched_terms"]
    return document
