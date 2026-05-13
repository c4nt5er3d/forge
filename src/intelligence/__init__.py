"""Local intelligence helpers for normalization, deduplication, and enrichment."""

from src.intelligence.dedup import dedup_documents
from src.intelligence.enricher import enrich_document
from src.intelligence.normalizer import normalize

__all__ = ["dedup_documents", "enrich_document", "normalize"]
