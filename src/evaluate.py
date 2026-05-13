import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Optional


@dataclass
class EvaluationCase:
    query: str
    expected: dict[str, Any]
    id: str = ""


@dataclass
class EvaluationRecord:
    case: EvaluationCase
    hit: bool
    rank: Optional[int]
    reciprocal_rank: float
    results: List[dict[str, Any]] = field(default_factory=list)


@dataclass
class EvaluationReport:
    records: List[EvaluationRecord]
    top_k: int

    @property
    def case_count(self) -> int:
        return len(self.records)

    @property
    def hit_count(self) -> int:
        return sum(1 for record in self.records if record.hit)

    @property
    def hit_rate(self) -> float:
        if not self.records:
            return 0.0
        return self.hit_count / len(self.records)

    @property
    def mrr(self) -> float:
        if not self.records:
            return 0.0
        return sum(record.reciprocal_rank for record in self.records) / len(self.records)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "forge-evaluation-report",
            "top_k": self.top_k,
            "case_count": self.case_count,
            "hit_count": self.hit_count,
            "hit_rate": self.hit_rate,
            "mrr": self.mrr,
            "records": [
                {
                    "id": record.case.id,
                    "query": record.case.query,
                    "expected": record.case.expected,
                    "hit": record.hit,
                    "rank": record.rank,
                    "reciprocal_rank": record.reciprocal_rank,
                    "results": record.results,
                }
                for record in self.records
            ],
        }


def load_evaluation_cases(path: Path) -> List[EvaluationCase]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
        rows = payload.get("cases", payload) if isinstance(payload, dict) else payload

    cases = []
    for index, row in enumerate(rows):
        query = row.get("query")
        expected = row.get("expected", {})
        if not query:
            raise ValueError(f"Evaluation case {index} is missing query")
        if not isinstance(expected, dict):
            raise ValueError(f"Evaluation case {index} expected field must be an object")
        cases.append(EvaluationCase(query=query, expected=expected, id=str(row.get("id", ""))))
    return cases


def _matches_value(actual: Any, expected: Any) -> bool:
    if actual is None:
        return False
    if isinstance(actual, list):
        return any(_matches_value(value, expected) for value in actual)
    return str(expected).lower() in str(actual).lower()


def result_matches(metadata: dict[str, Any], expected: dict[str, Any]) -> bool:
    if not expected:
        return False

    field_aliases = {
        "path": ["path", "source_path"],
        "source_path": ["path", "source_path"],
        "filename": ["name", "filename"],
        "name": ["name", "filename"],
        "document_id": ["document_id"],
        "chunk_id": ["chunk_id"],
    }

    for key, expected_value in expected.items():
        if key == "contains":
            haystack = " ".join(
                str(metadata.get(field, ""))
                for field in ["snippet", "_compressed_snippet", "name", "path", "document_id", "chunk_id"]
            )
            if not _matches_value(haystack, expected_value):
                return False
            continue

        aliases = field_aliases.get(key, [key])
        if not any(_matches_value(metadata.get(alias), expected_value) for alias in aliases):
            return False
    return True


def _summarize_result(metadata: dict[str, Any], score: float) -> dict[str, Any]:
    return {
        "name": metadata.get("name") or metadata.get("filename", ""),
        "path": metadata.get("path") or metadata.get("source_path", ""),
        "document_id": metadata.get("document_id", ""),
        "chunk_id": metadata.get("chunk_id", ""),
        "chunk_index": metadata.get("chunk_index"),
        "score": metadata.get("_score", score),
        "snippet": metadata.get("_compressed_snippet") or metadata.get("snippet", ""),
    }


def evaluate_cases(
    cases: Iterable[EvaluationCase],
    searcher: Any,
    top_k: int = 5,
    rerank: bool = False,
    compress: bool = False,
) -> EvaluationReport:
    records = []
    for case in cases:
        raw_results = searcher.search(case.query, top_k, rerank=rerank, compress=compress)
        summarized = [_summarize_result(metadata, score) for metadata, score in raw_results]
        rank = None
        for index, (metadata, _score) in enumerate(raw_results, start=1):
            if result_matches(metadata, case.expected):
                rank = index
                break
        records.append(
            EvaluationRecord(
                case=case,
                hit=rank is not None,
                rank=rank,
                reciprocal_rank=(1 / rank) if rank else 0.0,
                results=summarized,
            )
        )
    return EvaluationReport(records=records, top_k=top_k)


def render_markdown_report(report: EvaluationReport) -> str:
    lines = [
        "# Forge Evaluation Report",
        "",
        f"- Cases: `{report.case_count}`",
        f"- Hit rate: `{report.hit_rate:.3f}`",
        f"- MRR: `{report.mrr:.3f}`",
        f"- Top K: `{report.top_k}`",
        "",
        "## Cases",
    ]
    for record in report.records:
        status = "hit" if record.hit else "miss"
        lines.extend(
            [
                "",
                f"### {record.case.id or record.case.query}",
                f"- Query: `{record.case.query}`",
                f"- Status: `{status}`",
                f"- Rank: `{record.rank if record.rank is not None else 'none'}`",
                "",
            ]
        )
        for index, result in enumerate(record.results, start=1):
            lines.append(f"{index}. `{result['name']}` score `{float(result['score']):.3f}`")
    return "\n".join(lines).rstrip() + "\n"


def write_evaluation_report(report: EvaluationReport, output: Path, output_format: str = "json") -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        output.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        return
    if output_format == "markdown":
        output.write_text(render_markdown_report(report), encoding="utf-8")
        return
    raise ValueError(f"Unsupported evaluation format: {output_format}")
