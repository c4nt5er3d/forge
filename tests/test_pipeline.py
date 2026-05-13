import json
from pathlib import Path

from typer.testing import CliRunner

from src.main import app
from src.pipeline.extract import extract_document_text
from src.pipeline.chunker import chunk_text
from src.pipeline.ingest import Ingestor
from src.pipeline.validator import validate_document
from src.schema.document import Document
from src.state_manager import StateManager


def test_document_serializes_to_jsonl(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("Quarterly planning notes for product roadmap and budget.")

    document = Document.from_file(file_path, content="hello world", chunks=["hello world"])
    payload = json.loads(document.to_json_line())

    assert payload["filename"] == "notes.txt"
    assert payload["extension"] == ".txt"
    assert payload["content"] == "hello world"
    assert payload["chunks"] == ["hello world"]


def test_chunker_preserves_code_fences_and_tables():
    text = """Intro paragraph.

```python
def hello():
    return "world"
```

| Name | Value |
| --- | --- |
| Alpha | 1 |

Closing paragraph with enough words to be its own chunk."""

    chunks = chunk_text(text, max_chars=60)

    assert any(chunk.startswith("```python") and chunk.endswith("```") for chunk in chunks)
    assert any("| Name | Value |" in chunk and "| Alpha | 1 |" in chunk for chunk in chunks)


def test_chunker_supports_named_strategies():
    text = "First sentence. Second sentence has more detail.\n\nThird paragraph is separate."

    paragraph_chunks = chunk_text(text, max_chars=200, strategy="paragraph")
    sentence_chunks = chunk_text(text, max_chars=45, strategy="sentence")
    token_chunks = chunk_text(text, max_chars=30, strategy="token")

    assert paragraph_chunks == [text]
    assert any(chunk.startswith("First sentence.") for chunk in sentence_chunks)
    assert len(token_chunks) > 1


def test_chunker_rejects_unknown_strategy():
    try:
        chunk_text("hello", strategy="mystery")
    except ValueError as exc:
        assert "Unknown chunk strategy" in str(exc)
    else:
        raise AssertionError("unknown chunk strategy should fail")


def test_validator_records_quality_and_errors(tmp_path):
    file_path = tmp_path / "empty.txt"
    file_path.write_text("")
    document = Document.from_file(file_path, extraction_error="empty file")

    validated = validate_document(document)

    assert validated.quality_score == 0.0
    assert "empty_content" in validated.cleaning_log
    assert "extraction_error: empty file" in validated.cleaning_log


def test_state_manager_tracks_processed_and_modified_files(tmp_path):
    db_path = tmp_path / "state.db"
    file_path = tmp_path / "notes.txt"
    file_path.write_text("first version")
    state = StateManager(db_path)

    assert state.is_unchanged(file_path) is False
    state.mark_processed(file_path)
    assert state.is_unchanged(file_path) is True

    file_path.write_text("second version")
    assert state.is_unchanged(file_path) is False


def test_state_manager_marks_errored_status(tmp_path):
    file_path = tmp_path / "bad.bin"
    file_path.write_bytes(b"\x00\x01")
    state = StateManager(tmp_path / "state.db")

    state.mark_errored(file_path)

    assert state.get_status(file_path) == "errored"


def test_ingestor_emits_documents_and_skips_unchanged(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    file_path = source / "notes.txt"
    file_path.write_text("Quarterly planning notes for product roadmap and budget priorities.")

    ingestor = Ingestor(state_manager=StateManager(tmp_path / "state.db"))
    first_run = list(ingestor.run(source))
    second_run = list(ingestor.run(source))

    assert len(first_run) == 1
    assert first_run[0].filename == "notes.txt"
    assert first_run[0].chunks
    assert second_run == []


def test_ingestor_emits_unsupported_file_with_error(tmp_path):
    file_path = tmp_path / "archive.bin"
    file_path.write_bytes(b"\x00\x01\x02")
    ingestor = Ingestor(state_manager=StateManager(tmp_path / "state.db"))

    docs = list(ingestor.run(file_path))

    assert len(docs) == 1
    assert docs[0].content == ""
    assert docs[0].extraction_error == "unsupported extension: .bin"


def test_pipeline_text_extraction_recovers_non_utf8_text(tmp_path):
    file_path = tmp_path / "latin.txt"
    file_path.write_bytes("Résumé planning notes for café budget approvals.".encode("latin-1"))

    result = extract_document_text(file_path)

    assert result.error is None
    assert "Résumé" in result.content


def test_ingestor_recursive_traversal(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "notes.md").write_text("Markdown notes about project planning and delivery.")
    ingestor = Ingestor(state_manager=StateManager(tmp_path / "state.db"))

    docs = list(ingestor.run(tmp_path, recursive=True))

    assert [doc.filename for doc in docs] == ["notes.md"]


def test_ingestor_preserves_markdown_structure_for_chunking(tmp_path):
    file_path = tmp_path / "notes.md"
    file_path.write_text(
        """Project planning notes with enough readable words for extraction quality.

```python
def plan():
    return "ship"
```

| Task | Owner |
| --- | --- |
| Ingest | Forge |
"""
    )
    ingestor = Ingestor(state_manager=StateManager(tmp_path / "state.db"))

    docs = list(ingestor.run(file_path))

    assert "```python" in docs[0].content
    assert any(chunk.startswith("```python") for chunk in docs[0].chunks)
    assert any("| Task | Owner |" in chunk for chunk in docs[0].chunks)


def test_ingestor_records_selected_chunk_strategy(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("First sentence. Second sentence. Third sentence with planning context.")
    ingestor = Ingestor(
        state_manager=StateManager(tmp_path / "state.db"),
        chunk_strategy="sentence",
        max_chunk_chars=35,
    )

    docs = list(ingestor.run(file_path))

    assert docs[0].metadata["chunk_strategy"] == "sentence"
    assert len(docs[0].chunks) > 1


def test_ingest_cli_writes_jsonl(tmp_path):
    runner = CliRunner()
    source = tmp_path / "source"
    source.mkdir()
    (source / "notes.txt").write_text("Quarterly planning notes for product roadmap and budget priorities.")
    output = tmp_path / "out.jsonl"
    state = tmp_path / "state.db"

    result = runner.invoke(app, ["ingest", str(source), "--output", str(output), "--state", str(state)])

    assert result.exit_code == 0
    lines = output.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["filename"] == "notes.txt"


def test_ingest_cli_accepts_chunk_strategy(tmp_path):
    runner = CliRunner()
    file_path = tmp_path / "notes.txt"
    file_path.write_text("First sentence. Second sentence. Third sentence with planning context.")
    output = tmp_path / "out.jsonl"
    state = tmp_path / "state.db"

    result = runner.invoke(
        app,
        [
            "ingest",
            str(file_path),
            "--output",
            str(output),
            "--state",
            str(state),
            "--chunk-strategy",
            "sentence",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output.read_text())
    assert payload["metadata"]["chunk_strategy"] == "sentence"


def test_chunk_cli_reports_counts(tmp_path):
    runner = CliRunner()
    file_path = tmp_path / "notes.txt"
    file_path.write_text("First sentence. Second sentence. Third sentence with planning context.")

    result = runner.invoke(app, ["chunk", str(file_path), "--strategy", "sentence", "--max-chars", "35"])

    assert result.exit_code == 0
    assert "strategy:" in result.output
    assert "notes.txt" in result.output


def test_validate_and_doctor_cli_smoke(tmp_path):
    runner = CliRunner()
    source = tmp_path / "source"
    source.mkdir()
    (source / "empty.txt").write_text("")

    validate_result = runner.invoke(app, ["validate", str(source)])
    doctor_result = runner.invoke(app, ["doctor"])

    assert validate_result.exit_code == 0
    assert "issues" in validate_result.output
    assert doctor_result.exit_code == 0
    assert "FORGE DOCTOR" in doctor_result.output
