import json

import pytest

from src.schema.document import Document
from src.server import ForgeService


class FakeSearch:
    def search(self, query, top_k=5, rerank=False, compress=False):
        assert query
        return [
            (
                {
                    "name": "budget.txt",
                    "path": "/tmp/budget.txt",
                    "snippet": "Budget planning approvals.",
                    "_score": 0.9,
                    "_dense_score": 0.8,
                    "_bm25_score": 1.0,
                    "_matched_terms": ["budget"],
                },
                0.9,
            )
        ][:top_k]


def _document(tmp_path, name="budget.txt", content="Budget planning approvals."):
    file_path = tmp_path / name
    file_path.write_text(content, encoding="utf-8")
    return Document.from_file(
        file_path,
        content=content,
        chunks=[content],
        metadata={"tags": ["budget"]},
        quality_score=0.5,
    )


def _jsonl(tmp_path, documents):
    path = tmp_path / "docs.jsonl"
    path.write_text("\n".join(document.to_json_line() for document in documents) + "\n", encoding="utf-8")
    return path


def test_service_health_reports_allowed_roots(tmp_path):
    service = ForgeService(allowed_roots=[tmp_path])

    health = service.health()

    assert health["status"] == "ok"
    assert health["allowed_roots"] == [str(tmp_path.resolve())]


def test_service_rejects_paths_outside_allowed_roots(tmp_path):
    service = ForgeService(allowed_roots=[tmp_path])

    with pytest.raises(ValueError, match="outside allowed roots"):
        service.pack(from_jsonl="/etc/passwd")


def test_service_pack_from_jsonl(tmp_path):
    doc = _document(tmp_path)
    jsonl_path = _jsonl(tmp_path, [doc])
    service = ForgeService(allowed_roots=[tmp_path])

    response = service.pack(from_jsonl=str(jsonl_path), token_budget=500, reserve_tokens=50)

    assert response["manifest"]["format"] == "forge-context-pack"
    assert response["entries"][0]["filename"] == "budget.txt"


def test_service_dataset_from_jsonl_dedups(tmp_path):
    first = _document(tmp_path, "first.txt", "Repeated content")
    second = _document(tmp_path, "second.txt", "Repeated content")
    jsonl_path = _jsonl(tmp_path, [first, second])
    service = ForgeService(allowed_roots=[tmp_path])

    response = service.dataset(from_jsonl=str(jsonl_path))

    assert response["manifest"]["format"] == "forge-dataset"
    assert response["manifest"]["duplicate_count"] == 1
    assert len(response["documents"]) == 1


def test_service_search_uses_configured_index_dir(tmp_path):
    calls = []

    def factory(index_dir):
        calls.append(index_dir)
        return FakeSearch()

    index_dir = tmp_path / "index"
    index_dir.mkdir()
    service = ForgeService(allowed_roots=[tmp_path], searcher_factory=factory)

    response = service.search("budget", limit=1, index_dir=str(index_dir))

    assert calls == [str(index_dir.resolve())]
    assert response["results"][0]["name"] == "budget.txt"


def test_service_evaluate_from_cases_file(tmp_path):
    cases_path = tmp_path / "cases.json"
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    cases_path.write_text(
        json.dumps([{"query": "budget", "expected": {"filename": "budget.txt"}}]),
        encoding="utf-8",
    )
    service = ForgeService(allowed_roots=[tmp_path], searcher_factory=lambda _index_dir: FakeSearch())

    response = service.evaluate(str(cases_path), limit=1, index_dir=str(index_dir))

    assert response["format"] == "forge-evaluation-report"
    assert response["hit_rate"] == 1.0
