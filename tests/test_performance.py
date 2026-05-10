import unittest
import shutil
import time
from pathlib import Path
import sys

# Add the project root to the path so we can import code
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.organizer import organize

class TestPerformance(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_perf_dir")
        self.test_dir.mkdir(exist_ok=True)
        self.dest_dir = self.test_dir / "dest"
        
        # Create 1000 files
        for i in range(1000):
            (self.test_dir / f"file_{i}.txt").touch()
            
    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        
    def test_large_directory(self):
        start_time = time.time()
        organize(
            target=self.test_dir,
            destination=self.dest_dir,
            dry_run=True, # testing speed of scanning and categorization
            recursive=False,
            exclude=[],
            categories={"Docs": [".txt"]},
            date_sort=False,
            copy_mode=False
        )
        duration = time.time() - start_time
        
        # Check if duration is acceptable (e.g. less than 5 seconds for 1000 files)
        self.assertLess(duration, 5.0)

if __name__ == "__main__":
    unittest.main()
