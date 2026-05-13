from typer.testing import CliRunner

from src.intelligence.dedup import dedup_documents
from src.intelligence.enricher import enrich_document
from src.intelligence.normalizer import normalize
from src.main import app
from src.pipeline.ingest import Ingestor
from src.schema.document import Document
from src.state_manager import StateManager


def test_normalizer_collapses_noise_but_preserves_tables_and_code():
    text = """Project      planning!!!!!!

```python
def ship():
    return "ok"
```

| Task | Owner |
| --- | --- |
| Ingest | Forge |
"""

    normalized, log = normalize(text)

    assert "Project planning!!!" in normalized
    assert "```python" in normalized
    assert "| Task | Owner |" in normalized
    assert "collapsed_whitespace" in log
    assert "trimmed_repeated_symbols" in log


def test_enricher_adds_tags_and_counts(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("Budget planning budget approvals delivery.")
    document = Document.from_file(file_path, content=file_path.read_text(), chunks=["one", "two"])

    enriched = enrich_document(document)

    assert enriched.metadata["word_count"] == 5
    assert enriched.metadata["chunk_count"] == 2
    assert enriched.metadata["tags"][0] == "budget"
    assert "enriched_terms" in enriched.cleaning_log


def test_dedup_documents_keeps_highest_quality_duplicate(tmp_path):
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    first_path.write_text("same content")
    second_path.write_text("same content")
    first = Document.from_file(first_path, content="same content", quality_score=0.2)
    second = Document.from_file(second_path, content="same content", quality_score=0.9)

    deduped = dedup_documents([first, second])

    assert len(deduped) == 1
    assert deduped[0].filename == "second.txt"


def test_ingestor_adds_normalized_enrichment_metadata(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("Budget     planning notes for budget approvals and delivery tracking.")
    ingestor = Ingestor(state_manager=StateManager(tmp_path / "state.db"))

    docs = list(ingestor.run(file_path))

    assert docs[0].content == "Budget planning notes for budget approvals and delivery tracking."
    assert docs[0].metadata["word_count"] == 9
    assert docs[0].metadata["tags"]


def test_clean_dupes_cli_reports_duplicates(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    content = "Duplicate budget planning notes for approvals and delivery tracking."
    (source / "one.txt").write_text(content)
    (source / "two.txt").write_text(content)
    runner = CliRunner()

    result = runner.invoke(app, ["clean", str(source), "--dupes"])

    assert result.exit_code == 0
    assert "duplicates found:" in result.output
    assert "1" in result.output
