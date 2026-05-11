import unittest
import os
import shutil
from pathlib import Path
import sys

# Add the project root to the path so we can import code
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.classifier import get_category, get_destination_path
from src.utils import resolve_collision, collect_files, undo_last
from src.config_loader import validate_categories
from src.organizer import organize

class TestFileOrganizer(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_temp_dir")
        self.test_dir.mkdir(exist_ok=True)
        self.categories = {
            "Images": [".jpg", ".png"],
            "Docs": [".pdf", ".txt"]
        }

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_get_category(self):
        self.assertEqual(get_category(".jpg", self.categories), "Images")
        self.assertEqual(get_category(".PNG", self.categories), "Images")
        self.assertEqual(get_category(".pdf", self.categories), "Docs")
        self.assertEqual(get_category(".exe", self.categories), "Misc")

    def test_resolve_collision(self):
        file_path = self.test_dir / "test.txt"
        file_path.touch()
        
        new_path = resolve_collision(file_path)
        self.assertEqual(new_path.name, "test_1.txt")
        
        (self.test_dir / "test_1.txt").touch()
        new_path = resolve_collision(file_path)
        self.assertEqual(new_path.name, "test_2.txt")

    def test_collect_files(self):
        (self.test_dir / "file1.txt").touch()
        (self.test_dir / "file2.jpg").touch()
        sub_dir = self.test_dir / "sub"
        sub_dir.mkdir()
        (sub_dir / "file3.pdf").touch()

        files = collect_files(self.test_dir, recursive=False)
        self.assertEqual(len(files), 2)
        filenames = [f.name for f in files]
        self.assertIn("file1.txt", filenames)
        self.assertIn("file2.jpg", filenames)

        files = collect_files(self.test_dir, recursive=True)
        self.assertEqual(len(files), 3)
        filenames = [f.name for f in files]
        self.assertIn("file3.pdf", filenames)

    def test_validate_categories(self):
        valid_config = {"Images": [".jpg"], "Docs": []}
        validate_categories(valid_config)

        with self.assertRaises(ValueError):
            validate_categories([1, 2, 3])

        with self.assertRaises(ValueError):
            validate_categories({"Images": ".jpg"})

        with self.assertRaises(ValueError):
            validate_categories({"Images": [123]})

    def test_get_destination_path(self):
        file_path = self.test_dir / "test.jpg"
        file_path.touch()
        dest_dir = Path("dest")

        dest = get_destination_path(file_path, dest_dir, self.categories, date_sort=False)
        self.assertEqual(dest, dest_dir / "Images" / "test.jpg")

        dest = get_destination_path(file_path, dest_dir, self.categories, date_sort=True)
        parts = dest.parts
        self.assertIn("Images", parts)
        self.assertTrue(any(len(p) == 4 and p.isdigit() for p in parts))
        self.assertTrue(any("-" in p for p in parts))

    def test_organize_copy(self):
        src_file = self.test_dir / "to_copy.txt"
        src_file.touch()
        dest_dir = self.test_dir / "destination"
        
        organize(self.test_dir, dest_dir, dry_run=False, recursive=False, exclude=[], categories=self.categories, date_sort=False, copy_mode=True)
        
        self.assertIn(src_file.name, [f.name for f in self.test_dir.iterdir()])
        self.assertTrue((dest_dir / "Docs" / "to_copy.txt").exists())

    def test_undo(self):
        # Ensure clean state
        history_dir = Path("history")
        history_dir.mkdir(exist_ok=True)
        cursor_file = history_dir / ".undo_cursor"
        if cursor_file.exists():
            cursor_file.unlink()

        src_file = self.test_dir / "to_undo.txt"
        src_file.touch()
        dest_dir = self.test_dir / "destination"

        organize(self.test_dir, dest_dir, dry_run=False, recursive=False, exclude=[], categories=self.categories, date_sort=False, copy_mode=False)

        moved_file = dest_dir / "Docs" / "to_undo.txt"
        self.assertTrue(moved_file.exists())
        self.assertFalse(src_file.exists())

        # Manually set cursor to the correct position (1, because we just made 1 move)
        cursor_file.write_text("1")

        undo_last()

        self.assertTrue(src_file.exists())
        self.assertFalse(moved_file.exists())

    def test_edge_case_no_permissions(self):
        from unittest.mock import patch
        src_file = self.test_dir / "no_perm.txt"
        src_file.touch()
        dest_dir = self.test_dir / "dest_no_perm"
        dest_dir.mkdir()
        
        # Simulate a PermissionError when shutil.move is called during organization
        with patch('shutil.move', side_effect=PermissionError):
            organize(self.test_dir, dest_dir, dry_run=False, recursive=False, exclude=[], categories=self.categories, date_sort=False, copy_mode=False)
            
        # Verify the file still exists in the source directory after the failed move
        self.assertIn(src_file.name, [f.name for f in self.test_dir.iterdir()])

if __name__ == "__main__":
    unittest.main()
