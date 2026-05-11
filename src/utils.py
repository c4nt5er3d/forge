import json
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

def print_ascii_banner() -> None:
    
    ascii_art = """
  ███████╗ ██████╗ ██████╗  ██████╗ ███████╗
  ██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝
  █████╗  ██║   ██║██████╔╝██║  ███╗█████╗  
  ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝  
  ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗
  ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝"""
    console.print(f"[#e8550a]{ascii_art}[/#e8550a]")
    console.print("  [#888888]    FILE ORGANIZATION & RETRIEVAL GENERATION ENGINE[/#888888]\n")

def print_custom_help() -> None:
    # Custom themed help screen that overrides the default Typer help.
    # This maintains visual consistency with the 'forge' brand.
    print_ascii_banner()
    
    # Help tooltip
    console.print("  [#5bc8f5] Tip:[/#5bc8f5] Use [#f5a623]--help[/#f5a623] with any command for detailed options\n")
    
    console.print("  [#2a2a2a]────────────────────────────────────────────────────────────[/#2a2a2a]")
    console.print("\n  [#444444]COMMANDS[/#444444]\n")
    
    commands = [
        ("organize", "--smart", "Organize files intelligently"),
        ("rename", "--smart", "Smart rename files in-place"),
        ("copy", "", "Copy and organize files"),
        ("search", '"query"', "Semantic file search"),
        ("watch", "", "Real-time folder monitoring"),
        ("undo", "", "Revert last operation"),
        ("train", "", "Train ML classifier"),
        ("index", "", "Index files for search"),
    ]
    
    for cmd, flag, desc in commands:
        prompt = "[#e8550a]›[/#e8550a]"
        name = "[#f5a623]forge[/#f5a623]"
        sub = f"[#ffffff]{cmd}[/#ffffff]"
        flag_str = f" [#5bc8f5]{flag}[/#5bc8f5]" if flag else ""
        description = f"[#555555]// {desc}[/#555555]"
        
        console.print(f"  {prompt} {name} {sub}{flag_str} {description}")
        
    console.print("\n  [#1e1e1e]────────────────────────────────────────────────────────────[/#1e1e1e]")
    console.print("  [#555555]v0.1.0  ·  python 3.10+  ·  built by[/#555555] [#e8550a]jay[/#e8550a]\n")
    console.print("  [#1a1a1a]╰──────────────────────────────────────────────────────────╯[/#1a1a1a]\n")

def resolve_collision(destination: Path) -> Path:
    # Recursively checks for filename availability to prevent accidental data loss.
    # Appends an incremental suffix (e.g. _1, _2) until a unique path is found.
    try:
        if not destination.exists():
            return destination
    except PermissionError:
        # If we can't even check if it exists, we return the original path 
        # and let the subsequent move/copy operation handle the failure.
        return destination
    
    counter: int = 1
    while True:
        new_dest: Path = destination.with_stem(f"{destination.stem}_{counter}")
        try:
            if not new_dest.exists():
                return new_dest
        except PermissionError:
            return new_dest
        counter += 1

def collect_files(target: Path, recursive: bool) -> List[Path]:
    # Generator-like list comprehension for gathering file paths.
    # We use rglob("*") for recursion to capture all nested structures efficiently.
    if recursive:
        return [f for f in target.rglob("*") if f.is_file()]
    else:
        return [f for f in target.iterdir() if f.is_file()]

def save_history(operations: List[Dict[str, str]], action_type: str) -> None:
    # Persists transaction logs in JSON format to support the 'undo' command.
    # Each run creates a timestamped file for granular rollback capabilities.
    history_dir: Path = Path(__file__).parent.parent / "history"
    history_dir.mkdir(exist_ok=True)
    
    timestamp: str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    history_file: Path = history_dir / f"history_{timestamp}.json"
    
    data: Dict[str, Any] = {
        "timestamp": timestamp,
        "action": action_type,
        "status": "active",
        "operations": operations
    }
    
    with open(history_file, "w") as f:
        json.dump(data, f, indent=4)
    
    logging.info(f"Transaction log saved: {history_file.name}")

def _active_history_logs(history_dir: Path) -> List[Path]:
    logs: List[Path] = []
    for log in sorted(history_dir.glob("history_*.json")):
        try:
            with open(log, "r") as f:
                if json.load(f).get("status") == "active":
                    logs.append(log)
        except Exception:
            logging.error(f"Failed to inspect history log: {log}")
    return logs

def _preview_history_log(log: Path) -> None:
    with open(log, "r") as f:
        data = json.load(f)
    action = data.get("action", "unknown")
    operations = data.get("operations", [])
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]would undo:[/#888888] [#ffffff]{log.name}[/#ffffff] [dim]({action}, {len(operations)} files)[/dim]")
    for op in reversed(operations):
        console.print(f"    [dim]{op.get('dest')} -> {op.get('src')}[/dim]")

def undo_last(preview: bool = False, steps: int = 1, history_dir: Optional[Path] = None) -> None:
    # Reverses the most recent file operations by finding the latest 'active' history log.
    history_dir = history_dir or Path(__file__).parent.parent / "history"
    if not history_dir.exists():
        console.print("  [bold red]Error:[/bold red] No history directory found.")
        return

    logs: List[Path] = _active_history_logs(history_dir)
    if not logs:
        console.print("  [yellow]Nothing left to undo.[/yellow]")
        return

    steps = max(1, steps)
    target_logs = list(reversed(logs))[:steps]

    if preview:
        console.print(f"  [#e8550a]›[/#e8550a] [yellow]Undo preview. No files will be changed.[/yellow]\n")
        for log in target_logs:
            _preview_history_log(log)
        console.print("")
        return

    total_undone = 0
    for target_log in target_logs:
        total_undone += _undo_history_log(target_log)
    
    console.print(f"\n  [#e8550a]›[/#e8550a] [#28c840]Undo finished![/#28c840] [#ffffff]{total_undone}[/#ffffff] files reverted.\n")

def _undo_history_log(target_log: Path) -> int:
    with open(target_log, "r") as f:
        data = json.load(f)

    console.print(f"  [#e8550a]›[/#e8550a] [#888888]undoing operation:[/#888888] [#ffffff]{target_log.name}[/#ffffff]\n")

    action: str = data["action"]
    operations: List[Dict[str, str]] = data["operations"]
    undone_count: int = 0

    # We process operations in reverse order to correctly handle nested moves/copies.
    for op in reversed(operations):
        src: Path = Path(op["src"])
        dest: Path = Path(op["dest"])

        try:
            if action == "move":
                if dest.exists():
                    src.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dest), str(src))
                    console.print(f"    [dim]Restored: {src.name}[/dim]")
                    undone_count += 1
                else:
                    console.print(f"    [dim]File not found at destination: {dest.name}[/dim]")
            elif action == "copy":
                if dest.exists():
                    dest.unlink()
                    console.print(f"    [dim]Deleted copy: {dest.name}[/dim]")
                    undone_count += 1
        except Exception as e:
            console.print(f"    [bold red]Failed to revert {dest.name}:[/bold red] [red]{e}[/red]")

    # Mark as undone
    data["status"] = "undone"
    with open(target_log, "w") as f:
        json.dump(data, f, indent=4)
    return undone_count
