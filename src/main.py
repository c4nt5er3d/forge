import sys
import typer
from pathlib import Path
from typing import List, Optional
from rich.console import Console

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.logger import setup_logging
from src.config_loader import load_all_configs
from src.utils import undo_last
from src.organizer import organize
from src.watcher import start_watcher

app = typer.Typer(
    name="File Organizer",
    help="An intelligent AI-powered desktop assistant with local-first processing.",
    add_completion=False,
    rich_markup_mode="rich"
)

console = Console()

@app.command(name="run")
def run_command(
    target: Optional[str] = typer.Option(None, "--target", "-t", help="Folder to organize"),
    destination: Optional[str] = typer.Option(None, "--destination", "-d", help="Where to put sorted folders"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview what would happen without moving anything"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Also organize files inside subfolders"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-e", help="File extensions to skip"),
    date_sort: bool = typer.Option(False, "--date-sort", help="Organize files into year/month subfolders"),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy files instead of moving them"),
    use_ai: bool = typer.Option(False, "--use-ai", help="Use AI for semantic categorization"),
    ai_rename: bool = typer.Option(False, "--ai-rename", help="Smart rename files based on content keywords"),
    rename_only: bool = typer.Option(False, "--rename-only", help="Rename files in place without moving them to category folders"),
    ollama: bool = typer.Option(False, "--ollama", help="Use local Ollama LLM instead of lightweight algorithms"),
    env: str = typer.Option("default", "--env", help="Environment to load config for")
) -> None:
    """
    [bold blue]Batch organize[/bold blue] files in a target directory.
    """
    setup_logging()
    
    config, categories = load_all_configs(env=env)

    target_str = target if target is not None else config.get("default_target", ".")
    target_path = Path(target_str).resolve()
    
    dest_str = destination if destination is not None else config.get("default_destination")
    destination_path = Path(dest_str).resolve() if dest_str else target_path

    exclude_list = exclude if exclude is not None else config.get("exclude", [])
    date_sort_mode = date_sort or config.get("date_sort", False)
    copy_mode = copy or config.get("copy_mode", False)

    if not target_path.exists() or not target_path.is_dir():
        console.print(f"[bold red]Error:[/bold red] Target path is not a valid directory: {target_path}")
        raise typer.Exit(1)

    console.print("\n[bold blue]Batch Organizer Configuration:[/bold blue]")
    console.print(f"  [cyan]Target:[/cyan]      {target_path}")
    console.print(f"  [cyan]Destination:[/cyan] {destination_path}")
    console.print(f"  [cyan]Dry run:[/cyan]     {dry_run}")
    console.print(f"  [cyan]Recursive:[/cyan]   {recursive}")
    console.print(f"  [cyan]Use AI:[/cyan]      {use_ai or ai_rename}")
    console.print(f"  [cyan]Rename only:[/cyan] {rename_only}")
    console.print(f"  [cyan]Use Ollama:[/cyan]  {ollama}")

    organize(target_path, destination_path, dry_run, recursive, exclude_list, categories, date_sort_mode, copy_mode, use_ai, ai_rename, rename_only, ollama)

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
    [bold green]Real-time watchdog[/bold green] to monitor and sort files automatically.
    """
    setup_logging()
    config, categories = load_all_configs(env=env)

    target_str = target if target is not None else config.get("default_target", ".")
    target_path = Path(target_str).resolve()
    
    dest_str = destination if destination is not None else config.get("default_destination")
    destination_path = Path(dest_str).resolve() if dest_str else target_path

    exclude_list = exclude if exclude is not None else config.get("exclude", [])
    date_sort_mode = date_sort or config.get("date_sort", False)
    copy_mode = copy or config.get("copy_mode", False)

    if not target_path.exists() or not target_path.is_dir():
        console.print(f"[bold red]Error:[/bold red] Target path is not a valid directory: {target_path}")
        raise typer.Exit(1)

    start_watcher(target_path, destination_path, exclude_list, categories, date_sort_mode, copy_mode)

@app.command(name="train")
def train_command(
    data_dir: str = typer.Argument(..., help="Path to an already organized directory to use as training data")
) -> None:
    """
    [bold magenta]Train[/bold magenta] the ML classifier using an organized folder.
    """
    setup_logging()
    data_path = Path(data_dir).resolve()
    
    try:
        from src.ml import MLClassifier
        classifier = MLClassifier()
        classifier.train(data_path)
    except ImportError:
        console.print("[bold red]Error:[/bold red] ML dependencies not installed. Please run [cyan]pip install scikit-learn joblib[/cyan]")
        raise typer.Exit(1)

@app.command(name="undo")
def undo_command() -> None:
    """
    [bold yellow]Undo[/bold yellow] the last organization operation.
    """
    setup_logging()
    undo_last()

@app.command(name="index")
def index_command(
    target: str = typer.Option(..., "--target", "-t", help="Folder to index for semantic search")
) -> None:
    """
    [bold cyan]Index files[/bold cyan] so you can search their contents using natural language.
    """
    setup_logging()
    target_path = Path(target).resolve()
    console.print(f"[bold green]Building semantic search index for:[/bold green] {target_path}")
    
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
        console.print("[bold green]Indexing complete! You can now use 'organizer search'.[/bold green]")
    except Exception as e:
        console.print(f"[red]Failed to build index: {e}[/red]")

@app.command(name="search")
def search_command(
    query: str = typer.Argument(..., help="Natural language search query"),
    limit: int = typer.Option(3, "--limit", "-l", help="Number of results to return")
) -> None:
    """
    [bold magenta]Search[/bold magenta] for files using natural language (e.g. 'tax forms from last year').
    """
    setup_logging()
    console.print(f"[cyan]Searching for:[/cyan] '{query}'...")
    
    try:
        from src.search import SemanticSearch
        searcher = SemanticSearch()
        results = searcher.search(query, limit)
        
        if not results:
            console.print("[yellow]No matches found or index is empty. Run 'organizer index' first![/yellow]")
            return
            
        console.print(f"\n[bold green]Top {len(results)} matches:[/bold green]\n")
        for metadata, distance in results:
            # lower L2 distance is better
            match_strength = max(0, 100 - (distance * 50)) 
            console.print(f"📄 [bold]{metadata['name']}[/bold] (Score: {match_strength:.1f})")
            console.print(f"   [dim]Path: {metadata['path']}[/dim]")
            console.print(f"   [italic]\"{metadata['snippet']}\"[/italic]\n")
            
    except Exception as e:
        console.print(f"[red]Search failed: {e}[/red]")

if __name__ == "__main__":
    app()