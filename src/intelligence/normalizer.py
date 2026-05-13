import re
from typing import List, Tuple


def _is_preserved_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") or stripped.startswith("```") or stripped.startswith(("-", "*", "1."))


def normalize(text: str) -> Tuple[str, List[str]]:
    """Clean common extraction noise while preserving structured text."""
    log: List[str] = []
    if not text:
        return "", ["empty_input"]

    normalized_lines = []
    changed_whitespace = False
    removed_noise = False

    for line in text.splitlines():
        if _is_preserved_line(line):
            normalized_lines.append(line.rstrip())
            continue

        cleaned = re.sub(r"([^\w\s])\1{4,}", r"\1\1\1", line)
        if cleaned != line:
            removed_noise = True
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned != line.strip():
            changed_whitespace = True
        if cleaned:
            normalized_lines.append(cleaned)

    normalized = "\n".join(normalized_lines).strip()
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    if changed_whitespace:
        log.append("collapsed_whitespace")
    if removed_noise:
        log.append("trimmed_repeated_symbols")
    return normalized, log
