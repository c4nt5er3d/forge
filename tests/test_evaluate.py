import json

from typer.testing import CliRunner

from src.evaluate import (
    EvaluationCase,
    evaluate_cases,
    load_evaluation_cases,
    result_matches,
    write_evaluation_report,
)
from src.main import app


class FakeSearch:
    def search(self, query, top_k=5, rerank=False, compress=False):
        assert top_k == 2
        if query == "budget planning":
            return [
                ({"name": "budget.txt", "path": "/tmp/budget.txt", "snippet": "budget planning"}, 0.9),
                ({"name": "roadmap.txt", "path": "/tmp/roadmap.txt", "snippet": "roadmap"}, 0.3),
            ]
        return [
            ({"name": "notes.txt", "path": "/tmp/notes.txt", "snippet": "misc notes"}, 0.4),
            ({"name": "roadmap.txt", "path": "/tmp/roadmap.txt", "snippet": "release roadmap"}, 0.2),
        ]


def test_load_evaluation_cases_json_and_jsonl(tmp_path):
    json_path = tmp_path / "cases.json"
    jsonl_path = tmp_path / "cases.jsonl"
    json_path.write_text(
        json.dumps({"cases": [{"id": "a", "query": "budget", "expected": {"filename": "budget.txt"}}]}),
        encoding="utf-8",
    )
    jsonl_path.write_text(
        json.dumps({"query": "roadmap", "expected": {"contains": "roadmap"}}) + "\n",
        encoding="utf-8",
    )

    assert load_evaluation_cases(json_path)[0].id == "a"
    assert load_evaluation_cases(jsonl_path)[0].query == "roadmap"


def test_result_matches_aliases_and_contains():
    metadata = {
        "name": "budget.txt",
        "path": "/tmp/budget.txt",
        "snippet": "Quarterly budget planning notes.",
    }

    assert result_matches(metadata, {"filename": "budget.txt"})
    assert result_matches(metadata, {"path": "budget.txt"})
    assert result_matches(metadata, {"contains": "planning"})
    assert not result_matches(metadata, {"filename": "roadmap.txt"})


def test_evaluate_cases_computes_hit_rate_and_mrr():
    cases = [
        EvaluationCase(query="budget planning", expected={"filename": "budget.txt"}, id="hit-first"),
        EvaluationCase(query="roadmap", expected={"filename": "roadmap.txt"}, id="hit-second"),
        EvaluationCase(query="missing", expected={"filename": "missing.txt"}, id="miss"),
    ]

    report = evaluate_cases(cases, FakeSearch(), top_k=2)

    assert report.case_count == 3
    assert report.hit_count == 2
    assert report.hit_rate == 2 / 3
    assert report.mrr == (1 + 0.5 + 0) / 3
    assert report.records[1].rank == 2


def test_write_evaluation_report_json_and_markdown(tmp_path):
    report = evaluate_cases(
        [EvaluationCase(query="budget planning", expected={"filename": "budget.txt"})],
        FakeSearch(),
        top_k=2,
    )
    json_output = tmp_path / "evaluation.json"
    markdown_output = tmp_path / "evaluation.md"

    write_evaluation_report(report, json_output, "json")
    write_evaluation_report(report, markdown_output, "markdown")

    assert json.loads(json_output.read_text(encoding="utf-8"))["hit_count"] == 1
    assert "# Forge Evaluation Report" in markdown_output.read_text(encoding="utf-8")


def test_evaluate_cli_writes_report(tmp_path, monkeypatch):
    runner = CliRunner()
    cases = tmp_path / "cases.json"
    output = tmp_path / "evaluation.json"
    cases.write_text(
        json.dumps([{"query": "budget planning", "expected": {"filename": "budget.txt"}}]),
        encoding="utf-8",
    )

    monkeypatch.setattr("src.search.SemanticSearch", lambda index_dir="models/search_index": FakeSearch())
    result = runner.invoke(
        app,
        ["evaluate", str(cases), "--output", str(output), "--limit", "2"],
    )

    assert result.exit_code == 0
    assert "Evaluation complete" in result.output
    assert json.loads(output.read_text(encoding="utf-8"))["hit_rate"] == 1.0
