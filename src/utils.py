import json
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from rich.console import Console

console = Console()

def resolve_collision(destination: Path) -> Path:
    """
    Generates a unique filename to avoid overwriting existing files.
    
    Args:
        destination: The desired destination path.
        
    Returns:
        A Path object with a unique filename (e.g., 'file_1.txt').
    """
    if not destination.exists():
        return destination
    counter: int = 1
    while True:
        new_dest: Path = destination.with_stem(f"{destination.stem}_{counter}")
        if not new_dest.exists():
            return new_dest
        counter += 1

def collect_files(target: Path, recursive: bool) -> List[Path]:
    """
    Collects all file paths within a target directory.
    
    Args:
        target: The directory to scan.
        recursive: If True, scans all subdirectories.
        
    Returns:
        A list of Path objects for all files found.
    """
    if recursive:
        return [f for f in target.rglob("*") if f.is_file()]
    else:
        return [f for f in target.iterdir() if f.is_file()]

def save_history(operations: List[Dict[str, str]], action_type: str) -> None:
    """
    Saves a JSON log of all file operations to allow for undo functionality.
    
    Args:
        operations: A list of dicts detailing 'src' and 'dest' paths.
        action_type: The type of action performed ('move' or 'copy').
    """
    history_dir: Path = Path(__file__).parent.parent / "history"
    history_dir.mkdir(exist_ok=True)
    
    timestamp: str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    history_file: Path = history_dir / f"history_{timestamp}.json"
    
    data: Dict[str, Any] = {
        "timestamp": timestamp,
        "action": action_type,
        "operations": operations
    }
    
    with open(history_file, "w") as f:
        json.dump(data, f, indent=4)
    
    logging.info(f"Transaction log saved: {history_file.name}")

def undo_last() -> None:
    """
    Reverts the last organization operation using the most recent history log.
    """
    history_dir: Path = Path(__file__).parent.parent / "history"
    if not history_dir.exists():
        console.print("[red]Error:[/red] No history directory found.")
        return

    logs: List[Path] = sorted(history_dir.glob("history_*.json"))
    if not logs:
        console.print("[yellow]Error:[/yellow] No history logs found.")
        return

    last_log: Path = logs[-1]
    console.print(f"[cyan]Undoing last run:[/cyan] {last_log.name}")

    with open(last_log, "r") as f:
        data: Dict[str, Any] = json.load(f)

    action: str = data["action"]
    operations: List[Dict[str, str]] = data["operations"]
    undone_count: int = 0

    for op in reversed(operations):
        src: Path = Path(op["src"])
        dest: Path = Path(op["dest"])

        try:
            if action == "move":
                if dest.exists():
                    src.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dest), str(src))
                    console.print(f"[dim]Restored: {src.name}[/dim]")
                    undone_count += 1
            elif action == "copy":
                if dest.exists():
                    dest.unlink()
                    console.print(f"[dim]Deleted copy: {dest.name}[/dim]")
                    undone_count += 1
        except Exception as e:
            console.print(f"[red]Failed to revert {dest.name}: {e}[/red]")

    console.print(f"\n[bold green]Undo finished.[/bold green] {undone_count} files reverted.")
    last_log.unlink()
