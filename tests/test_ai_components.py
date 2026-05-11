# tests/test_ai_components.py
from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest
from src.ml import MLClassifier
from src.search import SemanticSearch

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

