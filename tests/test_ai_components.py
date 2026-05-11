# tests/test_ai_components.py
from unittest.mock import patch
from pathlib import Path
import zipfile

from src.ml import MLClassifier
from src.search import SemanticSearch
from src.llm import LocalLLM, extract_text
from src.organizer import organize

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
