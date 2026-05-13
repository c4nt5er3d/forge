import json

from typer.testing import CliRunner

from src.dataset import prepare_dataset_documents, write_dataset
from src.main import app
from src.schema.document import Document


def _document(tmp_path, name, content, extraction_error=None, quality=0.5):
    file_path = tmp_path / name
    file_path.write_text(content, encoding="utf-8")
    return Document.from_file(
        file_path,
        content=content,
        chunks=[content] if content else [],
        metadata={"tags": ["dataset"]},
        quality_score=quality,
        extraction_error=extraction_error,
    )


def test_prepare_dataset_documents_skips_errors_and_dedups(tmp_path):
    docs = [
        _document(tmp_path, "first.txt", "Repeated content", quality=0.4),
        _document(tmp_path, "second.txt", "Repeated content", quality=0.8),
        _document(tmp_path, "broken.bin", "", extraction_error="unsupported file type"),
    ]

    output_docs, result = prepare_dataset_documents(docs)

    assert len(output_docs) == 1
    assert output_docs[0].filename == "second.txt"
    assert result.input_count == 3
    assert result.output_count == 1
    assert result.duplicate_count == 1
    assert result.skipped_error_count == 1


def test_write_dataset_jsonl_and_manifest(tmp_path):
    docs = [
        _document(tmp_path, "first.txt", "Alpha notes"),
        _document(tmp_path, "second.txt", "Beta notes"),
    ]
    output = tmp_path / "dataset.jsonl"

    result = write_dataset(docs, output, export_format="jsonl")

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    manifest = json.loads((tmp_path / "dataset.manifest.json").read_text(encoding="utf-8"))
    assert len(rows) == 2
    assert result.output_count == 2
    assert manifest["format"] == "forge-dataset"
    assert manifest["output_count"] == 2


def test_dataset_cli_from_folder(tmp_path):
    runner = CliRunner()
    source = tmp_path / "source"
    source.mkdir()
    (source / "one.txt").write_text("Dataset budget planning notes.", encoding="utf-8")
    (source / "two.txt").write_text("Dataset budget planning notes.", encoding="utf-8")
    output = tmp_path / "dataset.jsonl"

    result = runner.invoke(
        app,
        [
            "dataset",
            str(source),
            "--output",
            str(output),
            "--format",
            "jsonl",
        ],
    )

    assert result.exit_code == 0
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert "Dataset complete" in result.output
    assert (tmp_path / "dataset.manifest.json").exists()


def test_dataset_cli_rejects_semantic_without_dedup(tmp_path):
    runner = CliRunner()
    source = tmp_path / "source"
    source.mkdir()
    (source / "one.txt").write_text("Dataset notes.", encoding="utf-8")

    result = runner.invoke(app, ["dataset", str(source), "--no-dedup", "--semantic"])

    assert result.exit_code == 1
    assert "--semantic requires deduplication" in result.output
