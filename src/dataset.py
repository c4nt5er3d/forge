import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from src.exporters import export_documents
from src.intelligence.dedup import dedup_documents, semantic_dedup_documents
from src.schema.document import Document


@dataclass
class DatasetResult:
    input_count: int
    output_count: int
    duplicate_count: int
    skipped_error_count: int
    export_format: str
    output_path: Path
    semantic: bool = False

    def manifest(self) -> dict:
        return {
            "format": "forge-dataset",
            "export_format": self.export_format,
            "input_count": self.input_count,
            "output_count": self.output_count,
            "duplicate_count": self.duplicate_count,
            "skipped_error_count": self.skipped_error_count,
            "semantic_dedup": self.semantic,
            "output_path": str(self.output_path),
        }


def prepare_dataset_documents(
    documents: Iterable[Document],
    dedup: bool = True,
    semantic: bool = False,
    threshold: float = 0.97,
) -> tuple[List[Document], DatasetResult]:
    docs = list(documents)
    usable_docs = [doc for doc in docs if not doc.extraction_error]
    skipped_error_count = len(docs) - len(usable_docs)

    if dedup and semantic:
        output_docs = semantic_dedup_documents(usable_docs, threshold=threshold)
    elif dedup:
        output_docs = dedup_documents(usable_docs)
    else:
        output_docs = usable_docs

    result = DatasetResult(
        input_count=len(docs),
        output_count=len(output_docs),
        duplicate_count=len(usable_docs) - len(output_docs),
        skipped_error_count=skipped_error_count,
        export_format="",
        output_path=Path(""),
        semantic=semantic if dedup else False,
    )
    return output_docs, result


def write_dataset(
    documents: Iterable[Document],
    output: Path,
    export_format: str = "jsonl",
    dedup: bool = True,
    semantic: bool = False,
    threshold: float = 0.97,
    write_manifest: bool = True,
) -> DatasetResult:
    output_docs, result = prepare_dataset_documents(
        documents,
        dedup=dedup,
        semantic=semantic,
        threshold=threshold,
    )
    export_documents(output_docs, output, export_format)

    result.export_format = export_format
    result.output_path = output
    if write_manifest:
        manifest_path = output / "dataset_manifest.json" if output.is_dir() else output.with_suffix(".manifest.json")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(result.manifest(), indent=2), encoding="utf-8")
    return result
