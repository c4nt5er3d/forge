import csv
import json

from typer.testing import CliRunner

from src.exporters import export_documents, load_documents
from src.main import app
from src.schema.document import Document
from src.transform import TemplateEngine


def _document(tmp_path, name="notes.txt", content="Budget planning notes for approvals."):
    file_path = tmp_path / name
    file_path.write_text(content)
    doc = Document.from_file(
        file_path,
        content=content,
        chunks=[content],
        metadata={"tags": ["budget", "planning"], "chunk_count": 1},
        quality_score=0.5,
    )
    return doc


def test_export_documents_jsonl_csv_markdown_and_rag(tmp_path):
    doc = _document(tmp_path)

    jsonl = tmp_path / "out.jsonl"
    csv_path = tmp_path / "out.csv"
    markdown = tmp_path / "out.md"
    rag_dir = tmp_path / "rag"

    export_documents([doc], jsonl, "jsonl")
    export_documents([doc], csv_path, "csv")
    export_documents([doc], markdown, "markdown")
    export_documents([doc], rag_dir, "rag")

    assert json.loads(jsonl.read_text())["filename"] == "notes.txt"
    with open(csv_path, newline="", encoding="utf-8") as handle:
        assert next(csv.DictReader(handle))["filename"] == "notes.txt"
    assert "## notes.txt" in markdown.read_text()
    assert (rag_dir / "documents.jsonl").exists()
    assert json.loads((rag_dir / "manifest.json").read_text())["document_count"] == 1


def test_load_documents_from_jsonl(tmp_path):
    doc = _document(tmp_path)
    jsonl = tmp_path / "docs.jsonl"
    jsonl.write_text(doc.to_json_line() + "\n")

    docs = load_documents(from_jsonl=jsonl)

    assert len(docs) == 1
    assert docs[0].filename == "notes.txt"


def test_export_cli_from_folder_and_jsonl(tmp_path):
    runner = CliRunner()
    source = tmp_path / "source"
    source.mkdir()
    (source / "notes.txt").write_text("Budget planning notes for approvals and delivery tracking.")
    output = tmp_path / "export.csv"

    result = runner.invoke(app, ["export", str(source), "--format", "csv", "--output", str(output)])

    assert result.exit_code == 0
    assert output.exists()
    assert "Export complete" in result.output


def test_template_engine_lists_and_renders_builtin_template(tmp_path):
    doc = _document(tmp_path)
    engine = TemplateEngine()

    templates = engine.list_templates()
    prompt = engine.transform([doc], "summary")[0]["output"]

    assert "summary" in templates
    assert "Budget planning notes" in prompt
    assert "notes.txt" in prompt


def test_transform_cli_writes_jsonl(tmp_path):
    runner = CliRunner()
    source = tmp_path / "source"
    source.mkdir()
    (source / "notes.txt").write_text("Budget planning notes for approvals and delivery tracking.")
    output = tmp_path / "transform.jsonl"

    result = runner.invoke(
        app,
        ["transform", str(source), "--template", "summary", "--output", str(output)],
    )

    assert result.exit_code == 0
    payload = json.loads(output.read_text())
    assert payload["template"] == "summary"
    assert payload["filename"] == "notes.txt"


def test_template_list_cli():
    runner = CliRunner()

    result = runner.invoke(app, ["template", "list"])

    assert result.exit_code == 0
    assert "summary" in result.output
    assert "flashcards" in result.output
