import json

from typer.testing import CliRunner

from src.main import app
from src.mcp_server import ForgeMCPTools
from src.schema.document import Document
from src.server import ForgeService


class FakeSearch:
    def search(self, query, top_k=5, rerank=False, compress=False):
        return [
            (
                {
                    "name": "budget.txt",
                    "path": "/tmp/budget.txt",
                    "snippet": "Budget planning approvals.",
                    "_score": 0.9,
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


def test_mcp_tools_delegate_health_and_search(tmp_path):
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    service = ForgeService(allowed_roots=[tmp_path], searcher_factory=lambda _index_dir: FakeSearch())
    tools = ForgeMCPTools(service)

    health = tools.health()
    search = tools.search("budget", limit=1, index_dir=str(index_dir))

    assert health["status"] == "ok"
    assert search["results"][0]["name"] == "budget.txt"


def test_mcp_tools_delegate_pack_and_dataset(tmp_path):
    docs = [
        _document(tmp_path, "first.txt", "Repeated content"),
        _document(tmp_path, "second.txt", "Repeated content"),
    ]
    jsonl_path = _jsonl(tmp_path, docs)
    tools = ForgeMCPTools(ForgeService(allowed_roots=[tmp_path]))

    pack = tools.pack(from_jsonl=str(jsonl_path), include_markdown=True)
    dataset = tools.dataset(from_jsonl=str(jsonl_path))

    assert pack["manifest"]["format"] == "forge-context-pack"
    assert "# Forge Context Pack" in pack["markdown"]
    assert dataset["manifest"]["duplicate_count"] == 1


def test_mcp_tools_delegate_evaluate(tmp_path):
    cases_path = tmp_path / "cases.json"
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    cases_path.write_text(
        json.dumps([{"query": "budget", "expected": {"filename": "budget.txt"}}]),
        encoding="utf-8",
    )
    service = ForgeService(allowed_roots=[tmp_path], searcher_factory=lambda _index_dir: FakeSearch())
    tools = ForgeMCPTools(service)

    report = tools.evaluate(str(cases_path), limit=1, index_dir=str(index_dir))

    assert report["format"] == "forge-evaluation-report"
    assert report["hit_rate"] == 1.0


def test_mcp_cli_reports_missing_optional_dependency(monkeypatch):
    runner = CliRunner()

    def fail_start(allowed_roots=None):
        raise ImportError("mcp missing")

    monkeypatch.setattr("src.mcp_server.run_mcp_server", fail_start)

    result = runner.invoke(app, ["mcp"])

    assert result.exit_code == 1
    assert "Install MCP dependencies" in result.output
