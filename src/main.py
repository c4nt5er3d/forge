import warnings
warnings.filterwarnings("ignore")

import sys
import typer
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.logger import setup_logging
from src.config_loader import load_all_configs
from src.utils import undo_last, print_ascii_banner
from src.organizer import organize
from src.watcher import start_watcher

# Core CLI entry point using Typer.
# We use Typer for its excellent type-hint integration and automated help generation.
app = typer.Typer(
    name="F.O.R.G.E.",
    help="File Organization & Retrieval Generation Engine.\n\nA powerful, AI-driven filesystem manager.",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=False,
    context_settings={"help_option_names": ["--help", "-h"]}
)

@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    # If no command is provided, we default to the custom help screen
    # rather than the standard Typer auto-help to maintain our specific UI theme.
    if ctx.invoked_subcommand is None:
        from src.utils import print_custom_help
        print_custom_help()

console = Console()

def _run_organize(
    target: Optional[str],
    destination: Optional[str],
    dry_run: bool,
    recursive: bool,
    exclude: Optional[List[str]],
    date_sort: bool,
    copy: bool,
    use_ai: bool,
    ai_rename: bool,
    rename_only: bool,
    ollama: bool,
    env: str
) -> None:
    # Centralized orchestration for all 'organize' flavored commands.
    # This prevents drift between 'run', 'organize', 'copy', and 'rename' entry points.
    setup_logging()
    
    
    config, categories = load_all_configs(env=env)

    # Resolution logic: CLI flags take precedence over config.json defaults.
    target_str = target if target is not None else config.get("default_target", ".")
    target_path = Path(target_str).resolve()
    
    dest_str = destination if destination is not None else config.get("default_destination")
    destination_path = Path(dest_str).resolve() if dest_str else target_path

    exclude_list = exclude if exclude is not None else config.get("exclude", [])
    date_sort_mode = date_sort or config.get("date_sort", False)
    copy_mode = copy or config.get("copy_mode", False)

    if not target_path.exists() or not target_path.is_dir():
        console.print(f"  [bold red]Error:[/bold red] Target path is not a valid directory: {target_path}")
        raise typer.Exit(1)

    console.print("  [#444444]BATCH CONFIGURATION[/#444444]\n")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]target:[/#888888]      [#ffffff]{target_path}[/#ffffff]")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]destination:[/#888888] [#ffffff]{destination_path}[/#ffffff]")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]dry run:[/#888888]     [#5bc8f5]{dry_run}[/#5bc8f5]")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]recursive:[/#888888]   [#5bc8f5]{recursive}[/#5bc8f5]")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]use ai:[/#888888]      [#5bc8f5]{use_ai or ai_rename}[/#5bc8f5]")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]rename only:[/#888888] [#5bc8f5]{rename_only}[/#5bc8f5]")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]use ollama:[/#888888]  [#5bc8f5]{ollama}[/#5bc8f5]\n")

    organize(target_path, destination_path, dry_run, recursive, exclude_list, categories, date_sort_mode, copy_mode, use_ai, ai_rename, rename_only, ollama)

@app.command(name="run", hidden=True)
def run_command(
    target: Optional[str] = typer.Option(None, "--target", "-t", help="Folder to organize"),
    destination: Optional[str] = typer.Option(None, "--destination", "-d", help="Where to put sorted folders"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview what would happen without moving anything"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Also organize files inside subfolders"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-e", help="File extensions to skip"),
    date_sort: bool = typer.Option(False, "--date-sort", help="Organize files into year/month subfolders"),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy files instead of moving them"),
    use_ai: bool = typer.Option(False, "--use-ai", help="Enable semantic AI categorization"),
    ai_rename: bool = typer.Option(False, "--ai-rename", help="Enable smart file renaming (TF-IDF or LLM)"),
    rename_only: bool = typer.Option(False, "--rename-only", help="Rename files in place without sorting them into folders"),
    ollama: bool = typer.Option(False, "--ollama", help="Use local Ollama instead of lightweight mathematical algorithms"),
    env: str = typer.Option("default", "--env", help="Environment to load config for")
) -> None:
    """Batch organize files (legacy command)."""
    _run_organize(target, destination, dry_run, recursive, exclude, date_sort, copy, use_ai, ai_rename, rename_only, ollama, env)

@app.command(name="organize")
def organize_command(
    target: Optional[str] = typer.Option(None, "--target", "-t", help="Folder to organize"),
    destination: Optional[str] = typer.Option(None, "--destination", "-d", help="Where to put sorted folders"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview what would happen without moving anything"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Also organize files inside subfolders"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-e", help="File extensions to skip"),
    date_sort: bool = typer.Option(False, "--date-sort", help="Organize files into year/month subfolders"),
    use_ai: bool = typer.Option(True, "--use-ai", help="Enable semantic AI categorization"),
    ai_rename: bool = typer.Option(False, "--ai-rename", help="Enable smart file renaming (TF-IDF or LLM)"),
    ollama: bool = typer.Option(False, "--ollama", help="Use local Ollama"),
    env: str = typer.Option("default", "--env", help="Environment to load config for")
) -> None:
    """Sort files into categories automatically."""
    _run_organize(target, destination, dry_run, recursive, exclude, date_sort, False, use_ai, ai_rename, False, ollama, env)

@app.command(name="copy")
def copy_command(
    target: Optional[str] = typer.Option(None, "--target", "-t", help="Folder to copy from"),
    destination: Optional[str] = typer.Option(None, "--destination", "-d", help="Where to put copies"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview what would happen"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Also copy files inside subfolders"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-e", help="File extensions to skip"),
    date_sort: bool = typer.Option(False, "--date-sort", help="Organize into year/month subfolders"),
    env: str = typer.Option("default", "--env", help="Environment to load config for")
) -> None:
    """Copy and organize files without moving originals."""
    # Forces copy_mode=True to ensure source files remain untouched.
    _run_organize(target, destination, dry_run, recursive, exclude, date_sort, True, False, False, False, False, env)

@app.command(name="rename")
def rename_command(
    target: Optional[str] = typer.Option(None, "--target", "-t", help="Folder to rename files in"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview renames"),
    ollama: bool = typer.Option(True, "--ollama", help="Use local Ollama for smart renaming"),
    env: str = typer.Option("default", "--env", help="Environment to load config for")
) -> None:
    """Smart rename files with local LLM."""
    # Specialized flow that renames files in-place without moving them to category folders.
    _run_organize(target, None, dry_run, False, None, False, False, False, True, True, ollama, env)

@app.command(name="watch")
def watch_command(
    target: Optional[str] = typer.Option(None, "--target", "-t", help="Folder to monitor"),
    destination: Optional[str] = typer.Option(None, "--destination", "-d", help="Where to put sorted folders"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-e", help="File extensions to skip"),
    date_sort: bool = typer.Option(False, "--date-sort", help="Organize files into year/month subfolders"),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy files instead of moving them"),
    env: str = typer.Option("default", "--env", help="Environment to load config for")
) -> None:
    """
    Real-time watchdog to monitor and sort files automatically.
    """
    setup_logging()
    print_ascii_banner()
    config, categories = load_all_configs(env=env)

    target_str = target if target is not None else config.get("default_target", ".")
    target_path = Path(target_str).resolve()
    
    dest_str = destination if destination is not None else config.get("default_destination")
    destination_path = Path(dest_str).resolve() if dest_str else target_path

    exclude_list = exclude if exclude is not None else config.get("exclude", [])
    date_sort_mode = date_sort or config.get("date_sort", False)
    copy_mode = copy or config.get("copy_mode", False)

    if not target_path.exists() or not target_path.is_dir():
        console.print(f"  [bold red]Error:[/bold red] Target path is not a valid directory: {target_path}")
        raise typer.Exit(1)

    console.print("  [#444444]WATCHER CONFIGURATION[/#444444]\n")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]target:[/#888888]      [#ffffff]{target_path}[/#ffffff]")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]destination:[/#888888] [#ffffff]{destination_path}[/#ffffff]")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]date sort:[/#888888]    [#5bc8f5]{date_sort_mode}[/#5bc8f5]")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]copy mode:[/#888888]    [#5bc8f5]{copy_mode}[/#5bc8f5]\n")

    start_watcher(target_path, destination_path, exclude_list, categories, date_sort_mode, copy_mode)

@app.command(name="train")
def train_command(
    data_dir: str = typer.Argument(..., help="Path to an already organized directory to use as training data")
) -> None:
    """
    Train the ML classifier using an organized folder.
    """
    # We delay ML imports to keep the CLI responsive for non-ML tasks.
    setup_logging()
    print_ascii_banner()
    data_path = Path(data_dir).resolve()
    
    try:
        from src.ml import MLClassifier
        classifier = MLClassifier()
        console.print(f"  [#e8550a]›[/#e8550a] [#888888]training on:[/#888888] [#ffffff]{data_path}[/#ffffff]\n")
        classifier.train(data_path)
    except ImportError:
        console.print("  [bold red]Error:[/bold red] ML dependencies not installed. Please run [cyan]pip install scikit-learn joblib[/cyan]")
        raise typer.Exit(1)

@app.command(name="undo")
def undo_command() -> None:
    """
    Undo last organization operation.
    """
    setup_logging()
    undo_last()

@app.command(name="index")
def index_command(
    target: str = typer.Option(..., "--target", "-t", help="Folder to index for semantic search")
) -> None:
    """
    Index files so you can search their contents using natural language.
    """
    setup_logging()
    print_ascii_banner()
    target_path = Path(target).resolve()
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]building index for:[/#888888] [#ffffff]{target_path}[/#ffffff]\n")
    
    try:
        from src.search import SemanticSearch
        searcher = SemanticSearch()
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            searcher.build_index(target_path, progress)
        console.print("\n  [#28c840]✔ Indexing complete! You can now use 'forge search'.[/#28c840]\n")
    except Exception as e:
        console.print(f"  [bold red]Failed to build index:[/bold red] [red]{e}[/red]")

@app.command(name="search")
def search_command(
    query: str = typer.Argument(..., help="Natural language search query"),
    limit: int = typer.Option(3, "--limit", "-l", help="Number of results to return")
) -> None:
    """
    Search for files using natural language (e.g. 'tax forms from last year').
    """
    setup_logging()
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]searching for:[/#888888] [#ffffff]\"{query}\"[/#ffffff]\n")
    
    try:
        from src.search import SemanticSearch
        searcher = SemanticSearch()
        results = searcher.search(query, limit)
        
        if not results:
            console.print("  [yellow]No matches found or index is empty. Run 'forge index' first![/yellow]")
            return
            
        console.print(f"\n  [#444444]TOP {len(results)} MATCHES[/#444444]\n")
        for metadata, distance in results:
            # Cosine similarity = 1 - (L2_distance² / 2)
            cosine_sim = max(0, 1 - (distance ** 2) / 2)
            console.print(f"  [#e8550a]›[/#e8550a] [#f5a623]{metadata['name']}[/#f5a623] [#888888](Score: {cosine_sim:.2f})[/#888888]")
            console.print(f"    [#5bc8f5]Path:[/#5bc8f5] [#ffffff]{metadata['path']}[/#ffffff]")
            snippet_panel = Panel(
                Text(f"\"{metadata['snippet']}\"", style="dim"),
                border_style="dim",
                padding=(0, 1)
            )
            console.print(snippet_panel)
            console.print("\n") 
            
    except Exception as e:
        console.print(f"  [bold red]Search failed:[/bold red] [red]{e}[/red]")

if __name__ == "__main__":
    app()