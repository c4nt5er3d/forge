from dataclasses import dataclass
from typing import Iterable, List, Optional, Set

import numpy as np

from src.schema.document import Document


@dataclass
class DuplicateCluster:
    kept: Document
    duplicates: List[Document]
    score: float


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


def _normalize(vector) -> np.ndarray:
    array = np.array(vector).astype("float32")
    norm = np.linalg.norm(array)
    if norm == 0:
        return array
    return array / norm


def semantic_duplicate_clusters(
    documents: Iterable[Document],
    threshold: float = 0.97,
    model: Optional[object] = None,
) -> List[DuplicateCluster]:
    """Cluster near-duplicate documents by embedding cosine similarity."""
    docs = [doc for doc in documents if doc.content.strip()]
    if len(docs) < 2:
        return []

    if model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            return []
        model = SentenceTransformer("all-MiniLM-L6-v2")

    raw_embeddings = model.encode([doc.content for doc in docs])
    embeddings = [_normalize(embedding) for embedding in raw_embeddings]
    used: Set[int] = set()
    clusters: List[DuplicateCluster] = []

    for index, document in enumerate(docs):
        if index in used:
            continue
        members = [(index, document, 1.0)]
        for other_index in range(index + 1, len(docs)):
            if other_index in used:
                continue
            score = float(np.dot(embeddings[index], embeddings[other_index]))
            if score >= threshold:
                members.append((other_index, docs[other_index], score))

        if len(members) == 1:
            continue

        best_index, kept, _best_score = max(
            members,
            key=lambda item: (item[1].quality_score, len(item[1].content)),
        )
        duplicates = [member for member_index, member, _score in members if member_index != best_index]
        for member_index, _member, _score in members:
            used.add(member_index)
        clusters.append(
            DuplicateCluster(
                kept=kept,
                duplicates=duplicates,
                score=max(score for _member_index, _member, score in members if _member_index != best_index),
            )
        )

    return clusters


def semantic_dedup_documents(
    documents: Iterable[Document],
    threshold: float = 0.97,
    model: Optional[object] = None,
) -> List[Document]:
    docs = list(documents)
    clusters = semantic_duplicate_clusters(docs, threshold=threshold, model=model)
    duplicate_ids = {doc.id for cluster in clusters for doc in cluster.duplicates}
    return [doc for doc in docs if doc.id not in duplicate_ids]
