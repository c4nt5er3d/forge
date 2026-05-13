from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib

from pydantic import BaseModel, Field


class Document(BaseModel):
    """Stable JSONL contract for extracted file intelligence."""

    id: str
    source_path: str
    filename: str
    extension: str
    file_size: int
    modified_at: float
    content: str
    chunks: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    quality_score: float = 0.0
    cleaning_log: List[str] = Field(default_factory=list)
    extraction_error: Optional[str] = None
    embeddings_path: Optional[str] = None

    @classmethod
    def from_file(
        cls,
        file_path: Path,
        content: str = "",
        chunks: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        quality_score: float = 0.0,
        cleaning_log: Optional[List[str]] = None,
        extraction_error: Optional[str] = None,
        embeddings_path: Optional[str] = None,
    ) -> "Document":
        stat = file_path.stat()
        source_path = str(file_path.resolve())
        doc_id = hashlib.sha256(f"{source_path}:{stat.st_mtime}".encode("utf-8")).hexdigest()
        return cls(
            id=doc_id,
            source_path=source_path,
            filename=file_path.name,
            extension=file_path.suffix.lower(),
            file_size=stat.st_size,
            modified_at=stat.st_mtime,
            content=content,
            chunks=chunks or [],
            metadata=metadata or {},
            quality_score=quality_score,
            cleaning_log=cleaning_log or [],
            extraction_error=extraction_error,
            embeddings_path=embeddings_path,
        )

    def to_json_line(self) -> str:
        if hasattr(self, "model_dump_json"):
            return self.model_dump_json()
        return self.json()
