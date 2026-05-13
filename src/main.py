import warnings
warnings.filterwarnings("ignore")

import shutil
import sys
import tempfile
import typer
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.log_utils import setup_logging
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
    target: Path = typer.Argument(..., help="Folder to organize"),
    destination: Optional[Path] = typer.Argument(None, help="Destination folder"),
    preview: bool = typer.Option(False, "--preview", "-p", help="Show changes without moving files"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subdirectories"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-e", help="Skip files matching pattern"),
    date_sort: bool = typer.Option(False, "--date-sort", help="Organize by date"),
    smart: bool = typer.Option(False, "--smart", "-s", help="Use AI for categorization"),
    local: bool = typer.Option(False, "--local", "-l", help="Force local LLM (Ollama)"),
    env: str = typer.Option("default", "--env", help="Environment config")
) -> None:
    """Sort files into categories automatically."""
    dest = destination if destination else target
    _run_organize(target, dest, preview, recursive, exclude or [], date_sort, False, smart, False, False, local, env)

@app.command(name="copy")
def copy_command(
    source: Path = typer.Argument(..., help="Source folder"),
    destination: Path = typer.Argument(..., help="Destination folder"),
    preview: bool = typer.Option(False, "--preview", "-p", help="Show changes without copying"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subdirectories"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-e", help="Skip files"),
    date_sort: bool = typer.Option(False, "--date-sort", help="Organize by date"),
    env: str = typer.Option("default", "--env", help="Environment config")
) -> None:
    """Copy and organize files without moving originals."""
    _run_organize(source, destination, preview, recursive, exclude or [], date_sort, True, False, False, False, False, env)

@app.command(name="rename")
def rename_command(
    target: Path = typer.Argument(..., help="Folder to rename files in"),
    preview: bool = typer.Option(False, "--preview", "-p", help="Show renames without applying"),
    smart: bool = typer.Option(False, "--smart", "-s", help="Use AI for smart renaming"),
    local: bool = typer.Option(False, "--local", "-l", help="Use local LLM (Ollama)"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subdirectories"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-e", help="Skip files"),
    env: str = typer.Option("default", "--env", help="Environment config")
) -> None:
    """Smart rename files in-place using AI."""
    _run_organize(target, target, preview, recursive, exclude or [], False, False, False, True, True, local, env)

@app.command(name="watch")
def watch_command(
    target: Path = typer.Argument(..., help="Folder to monitor"),
    destination: Optional[Path] = typer.Argument(None, help="Destination folder"),
    smart: bool = typer.Option(False, "--smart", "-s", help="Use AI categorization"),
    local: bool = typer.Option(False, "--local", "-l", help="Use local LLM"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Watch subdirectories"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-e", help="Skip files"),
    date_sort: bool = typer.Option(False, "--date-sort", help="Organize by date"),
    env: str = typer.Option("default", "--env", help="Environment config")
) -> None:
    """Real-time folder monitoring and organization."""
    setup_logging()
    config, categories = load_all_configs(env=env)
    dest = destination if destination else target
    exclude_list = exclude if exclude is not None else config.get("exclude", [])
    date_sort_mode = date_sort or config.get("date_sort", False)
    copy_mode = config.get("copy_mode", False)
    start_watcher(target.resolve(), dest.resolve(), exclude_list, categories, date_sort_mode, copy_mode, recursive=recursive)

@app.command(name="undo")
def undo_command(
    preview: bool = typer.Option(False, "--preview", "-p", help="Show what would be reverted"),
    steps: int = typer.Option(1, "--steps", "-n", help="Number of operations to undo")
) -> None:
    """Undo last organization operation."""
    from src.utils import undo_last
    undo_last(preview=preview, steps=steps)

@app.command(name="train")
def train_command(
    data_dir: Path = typer.Argument(..., help="Folder for training"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subdirectories"),
    env: str = typer.Option("default", "--env", help="Environment config")
) -> None:
    """Train the ML classifier."""
    from src.ml import MLClassifier
    classifier = MLClassifier()
    classifier.train(data_dir)

@app.command(name="ingest")
def ingest_command(
    target: Path = typer.Argument(..., help="File or folder to ingest"),
    output: Path = typer.Option(Path("output.jsonl"), "--output", "-o", help="JSONL output path"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subdirectories"),
    state: Optional[Path] = typer.Option(None, "--state", help="SQLite state database path")
) -> None:
    """Extract files into Document JSONL without moving source files."""
    setup_logging()
    if not target.exists():
        console.print(f"  [bold red]Error:[/bold red] Target does not exist: {target}")
        raise typer.Exit(1)

    from src.pipeline.ingest import Ingestor
    from src.state_manager import StateManager

    output.parent.mkdir(parents=True, exist_ok=True)
    ingestor = Ingestor(state_manager=StateManager(state) if state else None)
    written = 0
    with open(output, "w", encoding="utf-8") as jsonl:
        for document in ingestor.run(target.resolve(), recursive=recursive):
            jsonl.write(document.to_json_line() + "\n")
            written += 1

    console.print(f"  [#e8550a]›[/#e8550a] [#28c840]Ingest complete:[/#28c840] [#ffffff]{written}[/#ffffff] documents -> [#ffffff]{output}[/#ffffff]")

@app.command(name="validate")
def validate_command(
    target: Path = typer.Argument(..., help="File or folder to validate"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subdirectories")
) -> None:
    """Validate extraction quality without moving files or updating ingest state."""
    setup_logging()
    if not target.exists():
        console.print(f"  [bold red]Error:[/bold red] Target does not exist: {target}")
        raise typer.Exit(1)

    from src.pipeline.ingest import Ingestor
    from src.state_manager import StateManager

    with tempfile.TemporaryDirectory() as temp_dir:
        ingestor = Ingestor(state_manager=StateManager(Path(temp_dir) / "state.db"), use_state=False)
        docs = list(ingestor.run(target.resolve(), recursive=recursive))
    failures = [doc for doc in docs if doc.extraction_error]

    console.print(f"  [#e8550a]›[/#e8550a] [#888888]validated:[/#888888] [#ffffff]{len(docs)}[/#ffffff] documents")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]issues:[/#888888]    [#ffffff]{len(failures)}[/#ffffff]")
    for doc in failures[:10]:
        console.print(f"    [yellow]{doc.filename}[/yellow]: {doc.extraction_error}")

@app.command(name="doctor")
def doctor_command() -> None:
    """Check optional local dependencies and search index health."""
    setup_logging()
    checks = []

    checks.append(("Tesseract binary", shutil.which("tesseract") is not None))
    checks.append(("Ollama binary", shutil.which("ollama") is not None))

    for label, module_name in [
        ("PyPDF2", "PyPDF2"),
        ("Pillow", "PIL"),
        ("pytesseract", "pytesseract"),
        ("sentence-transformers", "sentence_transformers"),
        ("faiss-cpu", "faiss"),
        ("pydantic", "pydantic"),
    ]:
        try:
            __import__(module_name)
            available = True
        except ImportError:
            available = False
        checks.append((label, available))

    search_index = Path("models/search_index/faiss.index")
    checks.append(("FAISS index file", search_index.exists()))
    state_db = Path.home() / ".forge" / "state.db"
    checks.append(("Ingest state DB", state_db.exists()))

    console.print("\n  [#444444]FORGE DOCTOR[/#444444]\n")
    for label, available in checks:
        status = "[#28c840]ok[/#28c840]" if available else "[#febc2e]missing[/#febc2e]"
        console.print(f"  [#e8550a]›[/#e8550a] [#888888]{label}:[/#888888] {status}")
    console.print(f"\n  [#e8550a]›[/#e8550a] [#888888]search index:[/#888888] [#ffffff]{search_index.resolve()}[/#ffffff]")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]state db:[/#888888]     [#ffffff]{state_db}[/#ffffff]")
    console.print("")

@app.command(name="clean")
def clean_command(
    target: Path = typer.Argument(..., help="File or folder to inspect"),
    dupes: bool = typer.Option(False, "--dupes", help="Report duplicate extracted documents"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subdirectories")
) -> None:
    """Inspect clean-up opportunities without deleting files."""
    setup_logging()
    if not target.exists():
        console.print(f"  [bold red]Error:[/bold red] Target does not exist: {target}")
        raise typer.Exit(1)
    if not dupes:
        console.print("  [yellow]No clean mode selected. Try --dupes.[/yellow]")
        return

    from src.intelligence.dedup import dedup_documents
    from src.pipeline.ingest import Ingestor
    from src.state_manager import StateManager

    with tempfile.TemporaryDirectory() as temp_dir:
        ingestor = Ingestor(state_manager=StateManager(Path(temp_dir) / "state.db"), use_state=False)
        docs = [doc for doc in ingestor.run(target.resolve(), recursive=recursive) if doc.content]

    deduped = dedup_documents(docs)
    duplicate_count = len(docs) - len(deduped)
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]documents scanned:[/#888888] [#ffffff]{len(docs)}[/#ffffff]")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]duplicates found:[/#888888] [#ffffff]{duplicate_count}[/#ffffff]")

@app.command(name="index")
def index_command(
    target: Path = typer.Argument(..., help="Folder to index"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subdirectories"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-e", help="Skip files"),
    env: str = typer.Option("default", "--env", help="Environment config")
) -> None:
    """Index files for semantic search."""
    setup_logging()
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
        searcher.build_index(target, progress, recursive=recursive, exclude=exclude or [])
    console.print("\n  [#28c840]Indexing complete. You can now use 'forge search'.[/#28c840]\n")

@app.command(name="search")
def search_command(
    query: str = typer.Argument(..., help="Natural language search query"),
    limit: int = typer.Option(3, "--limit", "-n", help="Number of results to return")
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
            if metadata.get("_score_type") == "hybrid":
                display_score = metadata.get("_score", distance)
            else:
                # Cosine similarity = 1 - (L2_distance² / 2)
                display_score = max(0, 1 - (distance ** 2) / 2)
            console.print(f"  [#e8550a]›[/#e8550a] [#f5a623]{metadata['name']}[/#f5a623] [#888888](Score: {display_score:.2f})[/#888888]")
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
