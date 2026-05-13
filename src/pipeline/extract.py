from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.llm import (
    TEXT_EXTENSIONS,
    UNSUPPORTED_CONTAINER_EXTENSIONS,
    extract_text,
    extract_text_from_image,
    is_usable_text,
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | IMAGE_EXTENSIONS | PDF_EXTENSIONS | DOCX_EXTENSIONS


@dataclass
class ExtractionResult:
    content: str
    error: Optional[str] = None


def extract_document_text(file_path: Path, max_chars: int = 2000) -> ExtractionResult:
    suffix = file_path.suffix.lower()
    if suffix in UNSUPPORTED_CONTAINER_EXTENSIONS:
        return ExtractionResult("", f"unsupported container extension: {suffix}")
    if suffix not in SUPPORTED_EXTENSIONS:
        return ExtractionResult("", f"unsupported extension: {suffix or '<none>'}")
    if file_path.stat().st_size == 0:
        return ExtractionResult("", "empty file")

    if suffix in TEXT_EXTENSIONS:
        try:
            content = file_path.read_text(encoding="utf-8")[:max_chars].strip()
        except UnicodeDecodeError as exc:
            try:
                from charset_normalizer import from_path
            except ImportError:
                return ExtractionResult("", f"encoding error: {exc}")

            match = from_path(file_path).best()
            if match is None:
                return ExtractionResult("", f"encoding detection failed: {exc}")
            content = str(match)[:max_chars].strip()
    else:
        content = extract_text(file_path, max_chars=max_chars)

    if not content:
        return ExtractionResult("", "no usable text extracted")
    if not is_usable_text(content):
        return ExtractionResult("", "no usable text extracted")
    return ExtractionResult(content, None)


__all__ = [
    "ExtractionResult",
    "extract_document_text",
    "extract_text",
    "extract_text_from_image",
    "is_usable_text",
]
