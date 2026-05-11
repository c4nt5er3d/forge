import unittest
import os
import shutil
import subprocess
from pathlib import Path

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_integration_env")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(exist_ok=True)
        self.src_dir = self.test_dir / "src"
        self.src_dir.mkdir()
        self.dest_dir = self.test_dir / "dest"
        self.dest_dir.mkdir()
        
        (self.src_dir / "file1.txt").touch()
        (self.src_dir / "file2.jpg").touch()
        
    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        
    def test_cli_execution(self):
        main_script = Path(__file__).parent.parent / "src" / "main.py"
        
        result = subprocess.run([
            "python3", str(main_script),
            "copy",
            "--target", str(self.src_dir),
            "--destination", str(self.dest_dir)
        ], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        
        copied_files = list(self.dest_dir.rglob("*.*"))
        self.assertGreaterEqual(len(copied_files), 2)

if __name__ == "__main__":
    unittest.main()
