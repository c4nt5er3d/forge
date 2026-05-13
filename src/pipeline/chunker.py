import re
from typing import List

from src.schema.document import Document


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _split_text_preserving_blocks(text: str) -> List[str]:
    lines = text.splitlines()
    blocks: List[str] = []
    current: List[str] = []
    in_code = False

    def flush_current() -> None:
        if current:
            blocks.append("\n".join(current).strip())
            current.clear()

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                current.append(line)
                in_code = False
                flush_current()
            else:
                flush_current()
                current.append(line)
                in_code = True
            index += 1
            continue

        if in_code:
            current.append(line)
            index += 1
            continue

        if _is_table_line(line):
            flush_current()
            table_lines = [line]
            index += 1
            while index < len(lines) and _is_table_line(lines[index]):
                table_lines.append(lines[index])
                index += 1
            blocks.append("\n".join(table_lines).strip())
            continue

        if stripped == "":
            flush_current()
        else:
            current.append(line)
        index += 1

    flush_current()
    return [block for block in blocks if block]


STRATEGIES = {"recursive", "paragraph", "sentence", "token"}


def _split_words_to_limit(text: str, max_chars: int) -> List[str]:
    chunks: List[str] = []
    words = text.split()
    current_words: List[str] = []
    current_len = 0
    for word in words:
        next_len = current_len + len(word) + (1 if current_words else 0)
        if current_words and next_len > max_chars:
            chunks.append(" ".join(current_words))
            current_words = [word]
            current_len = len(word)
        else:
            current_words.append(word)
            current_len = next_len
    if current_words:
        chunks.append(" ".join(current_words))
    return chunks


def _is_atomic_block(block: str) -> bool:
    return block.lstrip().startswith("```") or all(_is_table_line(line) for line in block.splitlines())


def _sentence_units(block: str) -> List[str]:
    return [unit.strip() for unit in re.split(r"(?<=[.!?])\s+", block.strip()) if unit.strip()]


def _units_for_strategy(block: str, strategy: str) -> List[str]:
    if strategy in {"recursive", "paragraph"}:
        return [block]
    if strategy == "sentence":
        return _sentence_units(block)
    if strategy == "token":
        return _split_words_to_limit(block, max_chars=250)
    raise ValueError(f"Unknown chunk strategy: {strategy}")


def chunk_text(text: str, max_chars: int = 1000, strategy: str = "recursive") -> List[str]:
    if not text:
        return []
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown chunk strategy: {strategy}")

    chunks: List[str] = []
    pending = ""

    for block in _split_text_preserving_blocks(text):
        if _is_atomic_block(block):
            if pending:
                chunks.append(pending.strip())
                pending = ""
            chunks.append(block)
            continue

        for unit in _units_for_strategy(block, strategy):
            if len(unit) > max_chars:
                if pending:
                    chunks.append(pending.strip())
                    pending = ""
                chunks.extend(_split_words_to_limit(unit, max_chars=max_chars))
                continue

            separator = " " if strategy == "sentence" else "\n\n"
            candidate = f"{pending}{separator}{unit}".strip() if pending else unit
            if pending and len(candidate) > max_chars:
                chunks.append(pending.strip())
                pending = unit
            else:
                pending = candidate

    if pending:
        chunks.append(pending.strip())

    return chunks


def chunk_document(document: Document, max_chars: int = 1000, strategy: str = "recursive") -> Document:
    document.chunks = chunk_text(document.content, max_chars=max_chars, strategy=strategy)
    document.metadata["chunk_strategy"] = strategy
    return document
