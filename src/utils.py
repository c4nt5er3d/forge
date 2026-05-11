import json
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
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
        ("organize", "--target", "Sort files into categories"),
        ("watch", "--target", "Monitor folder in real-time"),
        ("copy", "--target", "Copy and organize without moving originals"),
        ("rename", "--ollama", "Smart rename with local LLM"),
        ("search", '"query"', "Semantic file search"),
        ("undo", "", "Revert last operation"),
        ("train", "--data", "Train ML classifier"),
        ("index", "--target", "Index files for semantic search"),
    ]
    
    for cmd, flag, desc in commands:
        prompt = "[#e8550a]›[/#e8550a]"
        name = "[#f5a623]forge[/#f5a623]"
        sub = f"[#ffffff]{cmd}[/#ffffff]"
        flag_str = f" [#5bc8f5]{flag}[/#5bc8f5]" if flag else ""
        description = f"[#555555]// {desc}[/#555555]"
        
        console.print(f"  {prompt} {name} {sub}{flag_str} {description}")
        
    console.print("\n  [#1e1e1e]────────────────────────────────────────────────────────────[/#1e1e1e]")
    console.print("  [#555555]v1.0.0  ·  python 3.9+  ·  built by[/#555555] [#e8550a]jay[/#e8550a]\n")
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

def undo_last() -> None:
    # Reverses the most recent file operations by finding the latest 'active' history log.
    history_dir: Path = Path(__file__).parent.parent / "history"
    if not history_dir.exists():
        console.print("  [bold red]Error:[/bold red] No history directory found.")
        return

    logs: List[Path] = sorted(history_dir.glob("history_*.json"))
    
    # Find the latest active log
    target_log = None
    data = None
    for log in reversed(logs):
        with open(log, "r") as f:
            temp_data = json.load(f)
            if temp_data.get("status") == "active":
                target_log = log
                data = temp_data
                break
    
    if not target_log:
        console.print("  [yellow]Nothing left to undo.[/yellow]")
        return
        
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
        
    console.print(f"\n  [#e8550a]›[/#e8550a] [#28c840]Undo finished![/#28c840] [#ffffff]{undone_count}[/#ffffff] files reverted.\n")
