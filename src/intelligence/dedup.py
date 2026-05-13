from typing import Iterable, List, Set

from src.schema.document import Document


def dedup_documents(documents: Iterable[Document]) -> List[Document]:
    """Remove exact duplicate document content, keeping the highest-quality record."""
    best_by_fingerprint: dict[str, Document] = {}
    order: List[str] = []

    for document in documents:
        fingerprint = document.content.strip().lower() or document.id
        if fingerprint not in best_by_fingerprint:
            order.append(fingerprint)
            best_by_fingerprint[fingerprint] = document
            continue

        current = best_by_fingerprint[fingerprint]
        if document.quality_score > current.quality_score:
            best_by_fingerprint[fingerprint] = document

    kept_ids: Set[str] = set()
    deduped: List[Document] = []
    for fingerprint in order:
        document = best_by_fingerprint[fingerprint]
        if document.id in kept_ids:
            continue
        kept_ids.add(document.id)
        deduped.append(document)
    return deduped
