import time
import logging
import threading
import shutil
from pathlib import Path
from typing import List, Dict, Set

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from rich.console import Console

from src.classifier import get_destination_path
from src.utils import resolve_collision, save_history

try:
    from src.ml import MLClassifier
except ImportError:
    MLClassifier = None

console = Console()

class StableFileHandler(FileSystemEventHandler):
    """
    Handles file system events and debounces them to wait for stable file sizes.
    Filters out temporary files created by browsers during downloads.
    """
    def __init__(self, target_dir: Path, destination: Path, exclude: List[str], categories: Dict[str, List[str]], date_sort: bool, copy_mode: bool):
        self.target_dir = target_dir
        self.destination = destination
        self.excluded: Set[str] = {f".{e.lstrip('.').lower()}" for e in exclude}
        self.categories = categories
        self.date_sort = date_sort
        self.copy_mode = copy_mode
        self.temp_extensions = {".crdownload", ".part", ".tmp", ".download"}
        self.ml_classifier = MLClassifier() if MLClassifier is not None else None
        
        self.pending_files: Dict[Path, float] = {}
        self.lock = threading.Lock()
        
        # Start the background processor thread
        self.running = True
        self.processor_thread = threading.Thread(target=self._process_pending_files, daemon=True)
        self.processor_thread.start()

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._add_file(Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._add_file(Path(event.src_path))

    def _add_file(self, file_path: Path) -> None:
        if file_path.name.startswith("."):
            return  # Skip hidden files
        if file_path.suffix.lower() in self.excluded:
            return  # Skip excluded pattern-based ignores
        if file_path.suffix.lower() in self.temp_extensions:
            return  # Skip temporary download files
        
        # Debounce: Update the last modified time for the file
        with self.lock:
            self.pending_files[file_path] = time.time()

    def _process_pending_files(self) -> None:
        while self.running:
            time.sleep(1)
            current_time = time.time()
            files_to_process = []
            
            with self.lock:
                for file_path, last_seen in list(self.pending_files.items()):
                    # If 3 seconds have passed since the last file event, it is considered stable
                    if current_time - last_seen > 3.0:
                        files_to_process.append(file_path)
                        del self.pending_files[file_path]
                        
            for file_path in files_to_process:
                self._organize_file(file_path)

    def _organize_file(self, file: Path) -> None:
        if not file.exists() or not file.is_file():
            return

        dest_path: Path = get_destination_path(file, self.destination, self.categories, self.date_sort, self.ml_classifier)
        category_folder: Path = dest_path.parent
        dest_file: Path = resolve_collision(dest_path)

        rel_dest = category_folder.relative_to(self.destination) if self.destination in category_folder.parents else category_folder

        try:
            category_folder.mkdir(parents=True, exist_ok=True)
            if self.copy_mode:
                shutil.copy2(str(file), str(dest_file))
                console.print(f"  [#e8550a]›[/#e8550a] [#28c840]Watched & Copied:[/#28c840] [#ffffff]{file.name}[/#ffffff] [#888888]-> {rel_dest}/[/#888888]")
                logging.info(f"Watchdog Copied: {file.name} -> {rel_dest}/")
                save_history([{"src": str(file), "dest": str(dest_file)}], "copy")
            else:
                shutil.move(str(file), str(dest_file))
                console.print(f"  [#e8550a]›[/#e8550a] [#28c840]Watched & Moved:[/#28c840]  [#ffffff]{file.name}[/#ffffff] [#888888]-> {rel_dest}/[/#888888]")
                logging.info(f"Watchdog Moved: {file.name} -> {rel_dest}/")
                save_history([{"src": str(file), "dest": str(dest_file)}], "move")
        except PermissionError:
            # Re-add to pending to retry later if it's still locked by another process
            with self.lock:
                self.pending_files[file] = time.time()
        except Exception as e:
            console.print(f"  [bold red]Error moving {file.name}:[/bold red] [red]{e}[/red]")
            logging.error(f"Error moving {file.name}: {e}")

    def stop(self) -> None:
        self.running = False
        self.processor_thread.join()

def start_watcher(target: Path, destination: Path, exclude: List[str], categories: Dict[str, List[str]], date_sort: bool = False, copy_mode: bool = False) -> None:
    """
    Starts the watchdog monitoring service on the target directory.
    """
    event_handler = StableFileHandler(target, destination, exclude, categories, date_sort, copy_mode)
    observer = Observer()
    observer.schedule(event_handler, str(target), recursive=False)
    
    console.print(f"\n  [#444444]WATCHDOG SERVICE[/#444444]\n")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]monitoring:[/#888888]  [#ffffff]{target}[/#ffffff]")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]destination:[/#888888] [#ffffff]{destination}[/#ffffff]")
    console.print("  [#e8550a]›[/#e8550a] [#5bc8f5]Status: Running... (Press Ctrl+C to stop)[/#5bc8f5]\n")
    
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n  [#e8550a]›[/#e8550a] [yellow]Stopping Watchdog gracefully...[/yellow]\n")
        observer.stop()
        event_handler.stop()
    observer.join()
