# tests/test_ai_components.py
from unittest.mock import patch
from pathlib import Path
import zipfile
import numpy as np

from src.ml import MLClassifier
from src.search import SemanticSearch, compress_context
from src.llm import LocalLLM, extract_text
from src.organizer import organize
from src.pipeline.ingest import Ingestor
from src.state_manager import StateManager


class CountingEmbeddingModel:
    def __init__(self):
        self.calls = []

    def get_sentence_embedding_dimension(self):
        return 3

    def encode(self, texts):
        self.calls.extend(texts)
        vectors = []
        for text in texts:
            lowered = text.lower()
            if "budget" in lowered:
                vectors.append([1.0, 0.0, 0.0])
            elif "roadmap" in lowered:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return np.array(vectors, dtype="float32")


class FakeCrossEncoder:
    def __init__(self, _model_name):
        pass

    def predict(self, pairs):
        return np.array([
            10.0 if "roadmap" in passage.lower() else 1.0
            for _query, passage in pairs
        ], dtype="float32")

def test_ml_predict_returns_none_without_model():
    # Mocking model path to a non-existent file
    clf = MLClassifier(model_path=Path("/nonexistent/model.joblib"))
    # Verify result with no model loaded
    result, conf = clf.predict(Path("test_document.pdf"))
    assert result is None
    assert conf == 0.0

def test_search_returns_empty_on_empty_index():
    with patch('sentence_transformers.SentenceTransformer') as MockModel:
        # Configure mock dimension
        instance = MockModel.return_value
        instance.get_sentence_embedding_dimension.return_value = 384
        
        # Mocking index path to avoid real disk I/O for tests
        searcher = SemanticSearch(index_dir="/tmp/test_index")
        results = searcher.search("tax forms from last year", top_k=3)
        assert results == []

def test_search_model_loading_error():
    # Patch SentenceTransformer to raise an ImportError
    with patch('sentence_transformers.SentenceTransformer', side_effect=ImportError):
        searcher = SemanticSearch(index_dir="/tmp/test_index")
        assert searcher.model is None
        assert searcher.dimension == 384

def test_search_metadata_persists_embeddings_and_reloads_without_reencoding(tmp_path):
    model = CountingEmbeddingModel()
    source = tmp_path / "source"
    source.mkdir()
    doc = source / "budget.txt"
    doc.write_text("Quarterly budget report for planning and approvals.")

    with patch('sentence_transformers.SentenceTransformer', return_value=model):
        searcher = SemanticSearch(index_dir=str(tmp_path / "index"))
        searcher.build_index(source)

    assert "embedding" in next(iter(searcher.metadata.values()))
    encode_calls_after_build = len(model.calls)

    with patch('sentence_transformers.SentenceTransformer', return_value=model):
        reloaded = SemanticSearch(index_dir=str(tmp_path / "index"))

    assert len(model.calls) == encode_calls_after_build
    assert reloaded.index.ntotal == 1

def test_search_returns_result_with_persisted_embeddings(tmp_path):
    model = CountingEmbeddingModel()
    source = tmp_path / "source"
    source.mkdir()
    (source / "budget.txt").write_text("Quarterly budget report for planning and approvals.")
    (source / "roadmap.txt").write_text("Product roadmap notes for delivery milestones.")

    with patch('sentence_transformers.SentenceTransformer', return_value=model):
        searcher = SemanticSearch(index_dir=str(tmp_path / "index"))
        searcher.build_index(source)
        results = searcher.search("budget planning", top_k=1)

    assert results
    assert results[0][0]["name"] == "budget.txt"

def test_search_hybrid_bm25_can_promote_exact_keyword_match(tmp_path):
    model = CountingEmbeddingModel()
    source = tmp_path / "source"
    source.mkdir()
    (source / "semantic.txt").write_text("General notes about planning and approvals.")
    (source / "keyword.txt").write_text("ZEBRA-99 incident report with exact tracking identifier.")

    with patch('sentence_transformers.SentenceTransformer', return_value=model):
        searcher = SemanticSearch(index_dir=str(tmp_path / "index"))
        searcher.build_index(source)
        results = searcher.search("ZEBRA-99", top_k=1)

    assert results[0][0]["name"] == "keyword.txt"
    assert results[0][0]["_bm25_score"] > 0

def test_index_uses_ingest_chunks_with_document_metadata(tmp_path):
    model = CountingEmbeddingModel()
    source = tmp_path / "source"
    source.mkdir()
    (source / "structured.md").write_text(
        "Budget planning overview.\n\n"
        "Roadmap delivery details with enough words for extraction quality."
    )

    with patch('sentence_transformers.SentenceTransformer', return_value=model):
        searcher = SemanticSearch(index_dir=str(tmp_path / "index"))
        indexed = searcher.build_index(source)
        results = searcher.search("roadmap delivery", top_k=1)

    assert indexed >= 1
    meta = results[0][0]
    assert meta["index_level"] == "chunk"
    assert "document_id" in meta
    assert "chunk_id" in meta
    assert "quality_score" in meta
    assert isinstance(meta["tags"], list)

def test_index_records_selected_chunk_strategy(tmp_path):
    model = CountingEmbeddingModel()
    source = tmp_path / "source"
    source.mkdir()
    (source / "notes.txt").write_text("First sentence. Second sentence. Third sentence with budget planning.")

    with patch('sentence_transformers.SentenceTransformer', return_value=model):
        searcher = SemanticSearch(index_dir=str(tmp_path / "index"))
        indexed = searcher.build_index(source, chunk_strategy="sentence")
        results = searcher.search("budget planning", top_k=1)

    assert indexed == 1
    assert results[0][0]["chunk_strategy"] == "sentence"

def test_search_rerank_reorders_candidates(tmp_path):
    model = CountingEmbeddingModel()
    source = tmp_path / "source"
    source.mkdir()
    (source / "budget.txt").write_text("Budget planning notes for approvals.")
    (source / "roadmap.txt").write_text("Roadmap delivery notes for milestones.")

    with patch('sentence_transformers.SentenceTransformer', return_value=model), \
         patch('sentence_transformers.CrossEncoder', FakeCrossEncoder):
        searcher = SemanticSearch(index_dir=str(tmp_path / "index"))
        searcher.build_index(source)
        results = searcher.search("budget planning", top_k=2, rerank=True)

    assert results[0][0]["name"] == "roadmap.txt"
    assert "_rerank_score" in results[0][0]

def test_search_rerank_falls_back_when_crossencoder_missing(tmp_path):
    model = CountingEmbeddingModel()
    source = tmp_path / "source"
    source.mkdir()
    (source / "budget.txt").write_text("Budget planning notes for approvals.")

    with patch('sentence_transformers.SentenceTransformer', return_value=model), \
         patch('sentence_transformers.CrossEncoder', side_effect=ImportError):
        searcher = SemanticSearch(index_dir=str(tmp_path / "index"))
        searcher.build_index(source)
        results = searcher.search("budget planning", top_k=1, rerank=True)

    assert results[0][0]["name"] == "budget.txt"
    assert "_rerank_score" not in results[0][0]

def test_search_uses_hyde_query_and_compressed_snippet(tmp_path):
    model = CountingEmbeddingModel()
    source = tmp_path / "source"
    source.mkdir()
    (source / "budget.txt").write_text(
        "Roadmap delivery notes are unrelated. "
        "Budget planning approvals explain payroll spending. "
        "Another unrelated sentence follows."
    )

    with patch('sentence_transformers.SentenceTransformer', return_value=model):
        searcher = SemanticSearch(index_dir=str(tmp_path / "index"))
        searcher.build_index(source)
        results = searcher.search(
            "payroll spending",
            top_k=1,
            compress=True,
            search_query="budget planning payroll spending approvals",
        )

    assert results[0][0]["_hyde_query"] == "budget planning payroll spending approvals"
    assert "Budget planning approvals" in results[0][0]["_compressed_snippet"]


def test_compress_context_prefers_query_relevant_sentences():
    text = (
        "Roadmap delivery notes are unrelated. "
        "Budget planning approvals explain payroll spending. "
        "Release checklist is separate."
    )

    compressed = compress_context(text, "payroll budget")

    assert compressed.startswith("Budget planning approvals")


def test_local_llm_hyde_query_falls_back_without_ollama():
    llm = LocalLLM(use_ollama=False)

    assert llm.hyde_query("budget planning") == "budget planning"

def test_index_from_jsonl_indexes_document_chunks(tmp_path):
    model = CountingEmbeddingModel()
    source = tmp_path / "source"
    source.mkdir()
    file_path = source / "budget.txt"
    file_path.write_text("Quarterly budget report for planning and approvals.")
    ingestor = Ingestor(state_manager=StateManager(tmp_path / "state.db"))
    jsonl_path = tmp_path / "docs.jsonl"
    jsonl_path.write_text("\n".join(doc.to_json_line() for doc in ingestor.run(source)))

    with patch('sentence_transformers.SentenceTransformer', return_value=model):
        searcher = SemanticSearch(index_dir=str(tmp_path / "index"))
        indexed = searcher.build_index_from_jsonl(jsonl_path)
        results = searcher.search("budget planning", top_k=1)

    assert indexed == 1
    assert results[0][0]["name"] == "budget.txt"
    assert results[0][0]["chunk_index"] == 0

def test_index_status_reports_counts(tmp_path):
    model = CountingEmbeddingModel()
    source = tmp_path / "source"
    source.mkdir()
    (source / "budget.txt").write_text("Quarterly budget report for planning and approvals.")

    with patch('sentence_transformers.SentenceTransformer', return_value=model):
        searcher = SemanticSearch(index_dir=str(tmp_path / "index"))
        searcher.build_index(source)
        status = searcher.index_status()

    assert status["index_exists"] is True
    assert status["metadata_exists"] is True
    assert status["counts_match"] is True
    assert status["chunk_records"] == 1

def test_local_smart_rename_generates_readable_title(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("Quarterly budget report for payroll expenses and travel reimbursement planning.")

    _category, new_name = LocalLLM().analyze_and_rename(file_path, ["Documents"])

    assert new_name is not None
    assert new_name.endswith(".txt")
    assert "Pk" not in new_name
    assert "Content_Types" not in new_name

def test_docx_extraction_uses_document_text_not_zip_artifacts(tmp_path):
    docx_path = tmp_path / "document.docx"
    document_xml = """
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>Annual planning report for product roadmap and budget priorities</w:t></w:r></w:p></w:body>
    </w:document>
    """
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr("[Content_Types].xml", "package metadata")
        archive.writestr("word/document.xml", document_xml)

    text = extract_text(docx_path)
    _category, new_name = LocalLLM().analyze_and_rename(docx_path, ["Documents"])

    assert "Annual planning report" in text
    assert new_name is not None
    assert "PK" not in new_name
    assert "Content_Types" not in new_name

def test_empty_or_unreadable_file_is_skipped_for_rename(tmp_path):
    file_path = tmp_path / "empty.txt"
    file_path.write_text("")

    organize(
        target=tmp_path,
        destination=tmp_path,
        dry_run=False,
        recursive=False,
        exclude=[],
        categories={"Documents": [".txt"]},
        rename_only=True,
        ai_rename=True,
    )

    assert file_path.exists()

def test_rename_preview_does_not_change_file(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("Quarterly budget report for payroll expenses and travel reimbursement planning.")

    organize(
        target=tmp_path,
        destination=tmp_path,
        dry_run=True,
        recursive=False,
        exclude=[],
        categories={"Documents": [".txt"]},
        rename_only=True,
        ai_rename=True,
    )

    assert file_path.exists()

def test_rename_collision_gets_numbered_name(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("Quarterly budget report for payroll expenses and travel reimbursement planning.")
    existing = tmp_path / "Quarterly_Budget_Report_Payroll.txt"
    existing.write_text("already here")

    organize(
        target=tmp_path,
        destination=tmp_path,
        dry_run=False,
        recursive=False,
        exclude=[],
        categories={"Documents": [".txt"]},
        rename_only=True,
        ai_rename=True,
    )

    assert existing.exists()
    assert (tmp_path / "Quarterly_Budget_Report_Payroll_1.txt").exists()

def test_train_reports_category_counts_and_few_examples(tmp_path, capsys):
    train_dir = tmp_path / "train"
    docs = train_dir / "Documents"
    images = train_dir / "Images"
    docs.mkdir(parents=True)
    images.mkdir()
    (docs / "one.txt").write_text("Business planning document with meeting notes.")
    (docs / "two.txt").write_text("Project delivery notes and budget planning.")
    (images / "image.jpg").write_text("fake image content")
    model_path = tmp_path / "classifier.joblib"

    classifier = MLClassifier(model_path=model_path)
    classifier.train(train_dir)
    output = capsys.readouterr().out

    assert "Documents" in output
    assert "Images" in output
    assert "few examples" in output
    assert "classifier.joblib" in output
