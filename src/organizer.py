import logging
import shutil
from pathlib import Path
from typing import List, Dict, Any, Set
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.console import Console

from src.utils import collect_files, resolve_collision, save_history
from src.classifier import get_destination_path

try:
    from src.ml import MLClassifier
except ImportError:
    MLClassifier = None

console = Console()

def organize(
    target: Path, 
    destination: Path, 
    dry_run: bool, 
    recursive: bool, 
    exclude: List[str], 
    categories: Dict[str, List[str]], 
    date_sort: bool = False, 
    copy_mode: bool = False,
    use_ai: bool = False,
    ai_rename: bool = False,
    rename_only: bool = False,
    use_ollama: bool = False
) -> None:
    """
    Main orchestration function to organize files based on extensions.
    
    Args:
        target: The directory containing files to organize.
        destination: The directory where organized folders will be created.
        dry_run: If True, simulates the process without moving/copying files.
        recursive: If True, searches all subdirectories of the target.
        exclude: A list of file extensions to ignore.
        categories: A dictionary mapping category names to lists of extensions.
        date_sort: If True, creates year/month subfolders.
        copy_mode: If True, copies files instead of moving them.
    """
    excluded: Set[str] = {f".{e.lstrip('.').lower()}" for e in exclude}

    with console.status("[bold green]Scanning directory for files...[/bold green]"):
        files: List[Path] = collect_files(target, recursive)

    if not files:
        console.print("[yellow]No files found to organize.[/yellow]")
        return

    moved: List[str] = []
    skipped: List[str] = []
    history_ops: List[Dict[str, str]] = []

    try:
        from src.llm import LocalLLM
    except ImportError:
        LocalLLM = None

    if rename_only:
        action_name = "Renaming"
    else:
        action_name = "Copying" if copy_mode else "Moving"

    ml_classifier = MLClassifier() if MLClassifier is not None else None
    local_llm = LocalLLM(use_ollama=use_ollama) if (LocalLLM is not None and (use_ai or ai_rename)) else None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        
        task = progress.add_task(f"[cyan]{action_name} files...", total=len(files))

        for file in files:
            if file.name.startswith("."):
                skipped.append(file.name)
                progress.advance(task)
                continue

            if file.suffix.lower() in excluded:
                logging.info(f"Excluded:  {file.name}")
                skipped.append(file.name)
                progress.advance(task)
                continue

            # Phase 4.1: AI Logic
            override_cat = None
            dest_name = file.name
            
            if local_llm is not None:
                progress.console.print(f"[dim]AI analyzing {file.name}...[/dim]")
                cat_guess, new_name = local_llm.analyze_and_rename(file, list(categories.keys()))
                if use_ai and cat_guess:
                    override_cat = cat_guess
                if ai_rename and new_name:
                    dest_name = new_name

            if rename_only:
                dest_path: Path = file.parent / dest_name
            else:
                dest_path: Path = get_destination_path(file, destination, categories, date_sort, ml_classifier, override_cat, dest_name)
                
            category_folder: Path = dest_path.parent
            dest_file: Path = resolve_collision(dest_path)

            if file == dest_file:
                progress.advance(task)
                continue

            rel_dest = category_folder.relative_to(destination) if destination in category_folder.parents else category_folder

            if dry_run:
                msg = f"[DRY RUN] {file.name} -> {rel_dest}/"
                logging.info(msg)
                progress.console.print(f"[dim]{msg}[/dim]")
            else:
                try:
                    category_folder.mkdir(parents=True, exist_ok=True)
                    if rename_only:
                        shutil.move(str(file), str(dest_file))
                        msg = f"Renamed:   {file.name} -> {dest_file.name}"
                        logging.info(msg)
                    elif copy_mode:
                        shutil.copy2(str(file), str(dest_file))
                        msg = f"Copied:    {file.name} -> {rel_dest}/"
                        logging.info(msg)
                    else:
                        shutil.move(str(file), str(dest_file))
                        msg = f"Moved:     {file.name} -> {rel_dest}/"
                        logging.info(msg)
                    
                    moved.append(file.name)
                    history_ops.append({
                        "src": str(file.resolve()),
                        "dest": str(dest_file.resolve())
                    })
                except PermissionError:
                    err = f"Permission denied: Could not move {file.name}"
                    logging.error(err)
                    progress.console.print(f"[red]{err}[/red]")
                    skipped.append(file.name)
                except Exception as e:
                    err = f"Error moving {file.name}: {e}"
                    logging.error(err)
                    progress.console.print(f"[red]{err}[/red]")
                    skipped.append(file.name)
            
            progress.advance(task)

    console.print("\n[bold]─── Summary ───────────────────────────[/bold]")
    if dry_run:
        console.print("[yellow]Dry run complete. No files were changed.[/yellow]")
    else:
        if rename_only:
            action_past = "renamed"
        else:
            action_past = "copied" if copy_mode else "moved"
            
        console.print(f"[green]Files {action_past}:[/green]   {len(moved)}")
        console.print(f"[yellow]Files skipped:[/yellow] {len(skipped)}")
        
        if history_ops:
            save_history(history_ops, "copy" if copy_mode else "move")
