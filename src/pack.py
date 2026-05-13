import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

from src.schema.document import Document


@dataclass
class PackEntry:
    document_id: str
    filename: str
    source_path: str
    chunk_index: int
    chunk_count: int
    text: str
    estimated_tokens: int
    quality_score: float
    tags: List[str] = field(default_factory=list)
    truncated: bool = False


@dataclass
class ContextPack:
    entries: List[PackEntry]
    token_budget: int
    reserve_tokens: int
    estimated_tokens: int
    skipped_chunks: int
    query: Optional[str] = None

    @property
    def available_tokens(self) -> int:
        return max(0, self.token_budget - self.reserve_tokens)

    @property
    def document_count(self) -> int:
        return len({entry.document_id for entry in self.entries})

    def manifest(self) -> dict:
        return {
            "format": "forge-context-pack",
            "token_budget": self.token_budget,
            "reserve_tokens": self.reserve_tokens,
            "available_tokens": self.available_tokens,
            "estimated_tokens": self.estimated_tokens,
            "document_count": self.document_count,
            "chunk_count": len(self.entries),
            "skipped_chunks": self.skipped_chunks,
            "query": self.query or "",
        }


def estimate_tokens(text: str) -> int:
    """Approximate LLM tokens without requiring a model-specific tokenizer."""
    if not text:
        return 0
    words = len(re.findall(r"\S+", text))
    by_chars = math.ceil(len(text) / 4)
    by_words = math.ceil(words * 1.3)
    return max(1, by_chars, by_words)


def _query_terms(query: Optional[str]) -> set[str]:
    if not query:
        return set()
    return {term for term in re.findall(r"[a-zA-Z0-9_]+", query.lower()) if len(term) > 2}


def _chunk_score(document: Document, text: str, chunk_index: int, terms: set[str]) -> float:
    if not terms:
        return -chunk_index

    lower_text = text.lower()
    tags = [str(tag).lower() for tag in document.metadata.get("tags", [])]
    matched_terms = sum(1 for term in terms if term in lower_text)
    tag_matches = sum(1 for term in terms if any(term in tag for tag in tags))
    density = matched_terms / max(1, estimate_tokens(text))
    return (
        matched_terms * 10
        + tag_matches * 3
        + density
        + document.quality_score
        - (chunk_index * 0.001)
    )


def _document_chunks(document: Document) -> List[str]:
    chunks = document.chunks if document.chunks else [document.content]
    return [chunk.strip() for chunk in chunks if chunk and chunk.strip()]


def _truncate_to_tokens(text: str, token_limit: int) -> str:
    if token_limit <= 0:
        return ""
    marker = "\n\n[truncated]"
    char_limit = max(1, (token_limit * 4) - len(marker))
    if estimate_tokens(text) <= token_limit:
        return text
    truncated = text[:char_limit].rstrip()
    last_space = truncated.rfind(" ")
    if last_space > char_limit * 0.75:
        truncated = truncated[:last_space].rstrip()
    candidate = f"{truncated}{marker}"
    while candidate and estimate_tokens(candidate) > token_limit:
        truncated = truncated[: max(0, len(truncated) - 16)].rstrip()
        if not truncated:
            return ""
        candidate = f"{truncated}{marker}"
    return candidate


def build_context_pack(
    documents: Iterable[Document],
    token_budget: int = 8000,
    reserve_tokens: int = 500,
    query: Optional[str] = None,
) -> ContextPack:
    if token_budget <= 0:
        raise ValueError("token_budget must be greater than zero")
    if reserve_tokens < 0:
        raise ValueError("reserve_tokens cannot be negative")
    if reserve_tokens >= token_budget:
        raise ValueError("reserve_tokens must be smaller than token_budget")

    terms = _query_terms(query)
    candidates = []
    skipped_chunks = 0

    for document_index, document in enumerate(documents):
        if document.extraction_error:
            continue
        chunks = _document_chunks(document)
        if not chunks:
            continue
        tags = [str(tag) for tag in document.metadata.get("tags", [])]
        for chunk_index, text in enumerate(chunks):
            candidates.append(
                (
                    _chunk_score(document, text, chunk_index, terms),
                    document_index,
                    chunk_index,
                    document,
                    text,
                    tags,
                    len(chunks),
                )
            )

    if terms:
        candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    else:
        candidates.sort(key=lambda item: (item[1], item[2]))

    available_tokens = token_budget - reserve_tokens
    used_tokens = 0
    entries: List[PackEntry] = []

    for _score, _document_index, chunk_index, document, text, tags, chunk_count in candidates:
        remaining = available_tokens - used_tokens
        if remaining <= 0:
            skipped_chunks += 1
            continue

        estimated = estimate_tokens(text)
        truncated = False
        if estimated > remaining:
            text = _truncate_to_tokens(text, remaining)
            estimated = estimate_tokens(text)
            truncated = True

        if not text or estimated > remaining:
            skipped_chunks += 1
            continue

        entries.append(
            PackEntry(
                document_id=document.id,
                filename=document.filename,
                source_path=document.source_path,
                chunk_index=chunk_index,
                chunk_count=chunk_count,
                text=text,
                estimated_tokens=estimated,
                quality_score=document.quality_score,
                tags=tags,
                truncated=truncated,
            )
        )
        used_tokens += estimated

    return ContextPack(
        entries=entries,
        token_budget=token_budget,
        reserve_tokens=reserve_tokens,
        estimated_tokens=used_tokens,
        skipped_chunks=skipped_chunks,
        query=query,
    )


def render_markdown_pack(pack: ContextPack) -> str:
    manifest = pack.manifest()
    lines = [
        "# Forge Context Pack",
        "",
        "```json",
        json.dumps(manifest, indent=2),
        "```",
        "",
        "## Sources",
    ]

    seen_sources = set()
    for entry in pack.entries:
        if entry.source_path in seen_sources:
            continue
        seen_sources.add(entry.source_path)
        lines.append(f"- `{entry.filename}`: `{entry.source_path}`")

    lines.append("")
    lines.append("## Context")
    for entry in pack.entries:
        tags = ", ".join(entry.tags) or "none"
        truncated = " yes" if entry.truncated else " no"
        lines.extend(
            [
                "",
                f"### {entry.filename} [{entry.chunk_index + 1}/{entry.chunk_count}]",
                f"- Path: `{entry.source_path}`",
                f"- Estimated tokens: `{entry.estimated_tokens}`",
                f"- Quality: `{entry.quality_score}`",
                f"- Tags: {tags}",
                f"- Truncated: `{truncated.strip()}`",
                "",
                entry.text,
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def write_context_pack(pack: ContextPack, output: Path, output_format: str = "markdown") -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "markdown":
        output.write_text(render_markdown_pack(pack), encoding="utf-8")
        return
    if output_format == "jsonl":
        rows = [{"type": "manifest", **pack.manifest()}]
        for entry in pack.entries:
            rows.append({"type": "context", **entry.__dict__})
        output.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )
        return
    raise ValueError(f"Unsupported pack format: {output_format}")
