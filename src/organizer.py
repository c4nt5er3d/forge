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

from concurrent.futures import ThreadPoolExecutor, as_completed

def _analyze_file(file, local_llm, categories, use_ai, ai_rename):
    if local_llm is None:
        return file, None, None
    cat_guess, new_name = local_llm.analyze_and_rename(file, list(categories.keys()))
    return file, cat_guess if use_ai else None, new_name if ai_rename else None

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
    # Orchestrates the core file movement/copying pipeline.
    # It balances AI-driven analysis with deterministic extension-based rules.
    excluded: Set[str] = {f".{e.lstrip('.').lower()}" for e in exclude}

    # Status indicator ensures the user knows the app is active during slow I/O scans.
    with console.status("  [#e8550a]›[/#e8550a] [#5bc8f5]Scanning directory for files...[/#5bc8f5]"):
        files: List[Path] = collect_files(target, recursive)

    if not files:
        console.print("  [#e8550a]›[/#e8550a] [yellow]No files found to organize.[/yellow]")
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

    # AI models are instantiated only when needed to save memory and startup time.
    ml_classifier = MLClassifier() if MLClassifier is not None else None
    local_llm = LocalLLM(use_ollama=use_ollama) if (LocalLLM is not None and (use_ai or ai_rename)) else None

    ai_results = {}
    if local_llm is not None:
        console.print("  [#e8550a]›[/#e8550a] [#5bc8f5]Analyzing files with AI (parallel)...[/#5bc8f5]")
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(_analyze_file, f, local_llm, categories, use_ai, ai_rename): f for f in files}
            for future in as_completed(futures):
                file, cat, name = future.result()
                ai_results[file] = (cat, name)

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
            # We skip hidden files to avoid messing with system/git configs.
            if file.name.startswith("."):
                skipped.append(file.name)
                progress.advance(task)
                continue

            if file.suffix.lower() in excluded:
                logging.info(f"Excluded:  {file.name}")
                skipped.append(file.name)
                progress.advance(task)
                continue

            # AI Logic: Attempts to infer category/name from file content.
            override_cat, dest_name = ai_results.get(file, (None, file.name))
            dest_name = dest_name or file.name

            if rename_only:
                # rename_only keeps files in their original directory.
                dest_path: Path = file.parent / dest_name
            else:
                dest_path: Path = get_destination_path(file, destination, categories, date_sort, ml_classifier, override_cat, dest_name)
                
            category_folder: Path = dest_path.parent
            if rename_only and dest_path == file:
                skipped.append(file.name)
                progress.advance(task)
                continue

            # resolve_collision handles the case where dest_path already exists (e.g. file_1.txt).
            dest_file: Path = resolve_collision(dest_path)

            if file == dest_file:
                # Skip if the file is already in the right place to avoid redundant I/O.
                skipped.append(file.name)
                progress.advance(task)
                continue

            rel_dest = category_folder.relative_to(destination) if destination in category_folder.parents else category_folder

            if dry_run:
                msg = rf"  [#e8550a]›[/#e8550a] [dim]\[DRY RUN] {file.name} -> {rel_dest}/[/dim]"
                logging.info(msg)
                progress.console.print(msg)
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
                    err = f"  [#e8550a]›[/#e8550a] [bold red]Permission denied:[/bold red] [red]Could not move {file.name}[/red]"
                    logging.error(err)
                    progress.console.print(err)
                    skipped.append(file.name)
                except Exception as e:
                    err = f"  [#e8550a]›[/#e8550a] [bold red]Error moving {file.name}:[/bold red] [red]{e}[/red]"
                    logging.error(err)
                    progress.console.print(err)
                    skipped.append(file.name)
            
            progress.advance(task)

    console.print("\n  [#444444]TRANSACTION SUMMARY[/#444444]\n")
    if dry_run:
        console.print("  [#e8550a]›[/#e8550a] [yellow]Dry run complete. No files were changed.[/yellow]")
    else:
        if rename_only:
            action_past = "renamed"
        else:
            action_past = "copied" if copy_mode else "moved"
            
        console.print(f"  [#e8550a]›[/#e8550a] [#28c840]Files {action_past}:[/#28c840]   [#ffffff]{len(moved)}[/#ffffff]")
        console.print(f"  [#e8550a]›[/#e8550a] [#febc2e]Files skipped:[/#febc2e] [#ffffff]{len(skipped)}[/#ffffff]")
        
        if history_ops:
            save_history(history_ops, "copy" if copy_mode else "move")
    console.print("")
