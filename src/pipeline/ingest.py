from pathlib import Path
from typing import Iterator, Optional

from src.intelligence.enricher import enrich_document
from src.intelligence.normalizer import normalize
from src.pipeline.chunker import chunk_document
from src.pipeline.extract import extract_document_text
from src.pipeline.validator import validate_document
from src.schema.document import Document
from src.state_manager import StateManager
from src.utils import collect_files


class Ingestor:
    def __init__(
        self,
        state_manager: Optional[StateManager] = None,
        max_extract_chars: int = 2000,
        max_chunk_chars: int = 1000,
        chunk_strategy: str = "recursive",
        use_state: bool = True,
    ):
        self.state_manager = state_manager if state_manager is not None else StateManager()
        self.max_extract_chars = max_extract_chars
        self.max_chunk_chars = max_chunk_chars
        self.chunk_strategy = chunk_strategy
        self.use_state = use_state

    def run(self, target: Path, recursive: bool = False) -> Iterator[Document]:
        files = collect_files(target, recursive=recursive) if target.is_dir() else [target]

        for file_path in files:
            if file_path.name.startswith(".") or ".git" in file_path.parts:
                continue
            if file_path.resolve() == self.state_manager.db_path.resolve():
                continue
            if self.use_state and self.state_manager.is_unchanged(file_path):
                continue

            result = extract_document_text(file_path, max_chars=self.max_extract_chars)
            content, cleaning_log = normalize(result.content)
            metadata = {"sha256": self.state_manager.file_sha256(file_path)}
            document = Document.from_file(
                file_path=file_path,
                content=content,
                metadata=metadata,
                cleaning_log=cleaning_log,
                extraction_error=result.error,
            )
            document = chunk_document(
                document,
                max_chars=self.max_chunk_chars,
                strategy=self.chunk_strategy,
            )
            document = validate_document(document)
            document = enrich_document(document)

            if self.use_state:
                if document.extraction_error:
                    self.state_manager.mark_errored(file_path)
                else:
                    self.state_manager.mark_processed(file_path)

            yield document
