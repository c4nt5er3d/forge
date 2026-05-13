import unittest
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch
from typer.testing import CliRunner

from src.main import app

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        self.src_dir = self.test_dir / "src"
        self.src_dir.mkdir()
        self.dest_dir = self.test_dir / "dest"
        self.dest_dir.mkdir()
        
        (self.src_dir / "file1.txt").touch()
        (self.src_dir / "file2.jpg").touch()
        
    def tearDown(self):
        self.temp_dir.cleanup()
        
    def test_cli_execution(self):
        main_script = Path(__file__).parent.parent / "src" / "main.py"
        
        result = subprocess.run([
            "python3", str(main_script),
            "copy",
            str(self.src_dir),
            str(self.dest_dir)
        ], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        
        copied_files = list(self.dest_dir.rglob("*.*"))
        self.assertGreaterEqual(len(copied_files), 2)


def test_index_command_uses_current_positional_cli(tmp_path, monkeypatch):
    runner = CliRunner()
    target = tmp_path / "source"
    target.mkdir()

    class FakeSearch:
        def build_index(self, target_dir, progress=None, recursive=True, exclude=None):
            assert target_dir == target
            assert progress is not None
            assert recursive is False
            assert exclude == []

    monkeypatch.setattr("src.search.SemanticSearch", lambda: FakeSearch())
    result = runner.invoke(app, ["index", str(target)])
    assert result.exit_code == 0


def test_index_command_supports_from_jsonl(tmp_path, monkeypatch):
    runner = CliRunner()
    jsonl_path = tmp_path / "docs.jsonl"
    jsonl_path.write_text("{}\n")

    class FakeSearch:
        def build_index_from_jsonl(self, path, progress=None):
            assert path == jsonl_path
            assert progress is not None
            return 2

    monkeypatch.setattr("src.search.SemanticSearch", lambda: FakeSearch())
    result = runner.invoke(app, ["index", "--from-jsonl", str(jsonl_path)])
    assert result.exit_code == 0
    assert "2" in result.output


def test_search_command_explain_prints_score_parts(monkeypatch):
    runner = CliRunner()

    class FakeSearch:
        def search(self, query, limit):
            return [({
                "name": "notes.txt",
                "path": "/tmp/notes.txt",
                "snippet": "budget planning",
                "index_level": "chunk",
                "chunk_index": 0,
                "chunk_count": 2,
                "_score_type": "hybrid",
                "_score": 0.75,
                "_dense_score": 0.5,
                "_bm25_score": 1.0,
                "_matched_terms": ["budget"],
                "tags": ["budget", "planning"],
            }, 0.75)]

    monkeypatch.setattr("src.search.SemanticSearch", lambda: FakeSearch())
    result = runner.invoke(app, ["search", "budget", "--explain"])
    assert result.exit_code == 0
    assert "dense:" in result.output
    assert "bm25:" in result.output
    assert "Chunk:" in result.output


def test_watch_command_loads_categories_and_starts_watcher(tmp_path):
    runner = CliRunner()
    target = tmp_path / "watch"
    dest = tmp_path / "dest"
    target.mkdir()
    dest.mkdir()

    with patch("src.main.start_watcher") as start_watcher:
        result = runner.invoke(app, ["watch", str(target), str(dest)])

    assert result.exit_code == 0
    args, kwargs = start_watcher.call_args
    assert args[0] == target.resolve()
    assert args[1] == dest.resolve()
    assert "Documents" in args[3]
    assert kwargs["recursive"] is False

if __name__ == "__main__":
    unittest.main()
