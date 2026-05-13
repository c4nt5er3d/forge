import csv
import json
import tempfile
from pathlib import Path
from typing import Iterable, List, Optional

from src.pipeline.ingest import Ingestor
from src.schema.document import Document
from src.state_manager import StateManager


def load_documents(
    target: Optional[Path] = None,
    from_jsonl: Optional[Path] = None,
    recursive: bool = False,
    chunk_strategy: str = "recursive",
) -> List[Document]:
    if from_jsonl is not None:
        documents = []
        for line in from_jsonl.read_text(encoding="utf-8").splitlines():
            if line.strip():
                documents.append(Document(**json.loads(line)))
        return documents

    if target is None:
        raise ValueError("target or from_jsonl is required")

    state_path = Path(tempfile.gettempdir()) / "forge_export_state.db"
    ingestor = Ingestor(
        state_manager=StateManager(state_path),
        chunk_strategy=chunk_strategy,
        use_state=False,
    )
    return list(ingestor.run(target.resolve(), recursive=recursive))


def _flatten_document(document: Document) -> dict:
    return {
        "id": document.id,
        "source_path": document.source_path,
        "filename": document.filename,
        "extension": document.extension,
        "file_size": document.file_size,
        "modified_at": document.modified_at,
        "quality_score": document.quality_score,
        "extraction_error": document.extraction_error or "",
        "tags": ";".join(document.metadata.get("tags", [])),
        "chunk_count": len(document.chunks),
        "content": document.content,
    }


def _write_jsonl(documents: Iterable[Document], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(document.to_json_line() for document in documents) + "\n",
        encoding="utf-8",
    )


def _write_csv(documents: Iterable[Document], output: Path) -> None:
    rows = [_flatten_document(document) for document in documents]
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", newline="", encoding="utf-8") as handle:
        fieldnames = list(rows[0].keys()) if rows else list(_flatten_document(_empty_document()).keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(documents: Iterable[Document], output: Path) -> None:
    parts = ["# Forge Export\n"]
    for document in documents:
        tags = ", ".join(document.metadata.get("tags", [])) or "none"
        parts.extend([
            f"## {document.filename}",
            f"- Path: `{document.source_path}`",
            f"- Quality: `{document.quality_score}`",
            f"- Tags: {tags}",
            f"- Extraction error: `{document.extraction_error or 'none'}`",
            "",
            document.content or "_No extracted content._",
            "",
        ])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts), encoding="utf-8")


def _write_parquet(documents: Iterable[Document], output: Path) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError("pyarrow is required for parquet export") from exc

    rows = [_flatten_document(document) for document in documents]
    table = pa.Table.from_pylist(rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, output)


def _write_rag_bundle(documents: Iterable[Document], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    docs = list(documents)
    _write_jsonl(docs, output / "documents.jsonl")
    manifest = {
        "format": "forge-rag-bundle",
        "document_count": len(docs),
        "chunk_count": sum(len(document.chunks) for document in docs),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _empty_document() -> Document:
    return Document(
        id="",
        source_path="",
        filename="",
        extension="",
        file_size=0,
        modified_at=0,
        content="",
    )


def export_documents(documents: Iterable[Document], output: Path, export_format: str) -> None:
    docs = list(documents)
    if export_format == "jsonl":
        _write_jsonl(docs, output)
    elif export_format == "csv":
        _write_csv(docs, output)
    elif export_format == "markdown":
        _write_markdown(docs, output)
    elif export_format == "parquet":
        _write_parquet(docs, output)
    elif export_format == "rag":
        _write_rag_bundle(docs, output)
    else:
        raise ValueError(f"Unsupported export format: {export_format}")
