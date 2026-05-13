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


def chunk_text(text: str, max_chars: int = 1000) -> List[str]:
    if not text:
        return []

    chunks: List[str] = []
    pending = ""

    for block in _split_text_preserving_blocks(text):
        is_atomic = block.lstrip().startswith("```") or all(_is_table_line(line) for line in block.splitlines())
        if is_atomic:
            if pending:
                chunks.append(pending.strip())
                pending = ""
            chunks.append(block)
            continue

        if len(block) > max_chars:
            if pending:
                chunks.append(pending.strip())
                pending = ""
            words = block.split()
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
            continue

        candidate = f"{pending}\n\n{block}".strip() if pending else block
        if pending and len(candidate) > max_chars:
            chunks.append(pending.strip())
            pending = block
        else:
            pending = candidate

    if pending:
        chunks.append(pending.strip())

    return chunks


def chunk_document(document: Document, max_chars: int = 1000) -> Document:
    document.chunks = chunk_text(document.content, max_chars=max_chars)
    return document
