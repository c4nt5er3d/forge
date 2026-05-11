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
