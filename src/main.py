import warnings
warnings.filterwarnings("ignore")

import json
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
template_app = typer.Typer(help="Manage local transform templates.")
app.add_typer(template_app, name="template")

@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    # If no command is provided, we default to the custom help screen
    # rather than the standard Typer auto-help to maintain our specific UI theme.
    if ctx.invoked_subcommand is None:
        from src.utils import print_custom_help
        print_custom_help()

console = Console()


def _default_export_output(export_format: str) -> Path:
    if export_format == "markdown":
        return Path("export.md")
    if export_format == "rag":
        return Path("rag_bundle")
    return Path(f"export.{export_format}")


def _default_pack_output(pack_format: str) -> Path:
    if pack_format == "jsonl":
        return Path("context_pack.jsonl")
    return Path("context_pack.md")


def _default_dataset_output(dataset_format: str) -> Path:
    if dataset_format == "rag":
        return Path("dataset_bundle")
    return Path(f"dataset.{dataset_format}")

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
    state: Optional[Path] = typer.Option(None, "--state", help="SQLite state database path"),
    chunk_strategy: str = typer.Option("recursive", "--chunk-strategy", help="Chunk strategy: recursive, paragraph, sentence, token")
) -> None:
    """Extract files into Document JSONL without moving source files."""
    setup_logging()
    if not target.exists():
        console.print(f"  [bold red]Error:[/bold red] Target does not exist: {target}")
        raise typer.Exit(1)

    from src.pipeline.ingest import Ingestor
    from src.state_manager import StateManager

    output.parent.mkdir(parents=True, exist_ok=True)
    ingestor = Ingestor(
        state_manager=StateManager(state) if state else None,
        chunk_strategy=chunk_strategy,
    )
    written = 0
    with open(output, "w", encoding="utf-8") as jsonl:
        for document in ingestor.run(target.resolve(), recursive=recursive):
            jsonl.write(document.to_json_line() + "\n")
            written += 1

    console.print(f"  [#e8550a]›[/#e8550a] [#28c840]Ingest complete:[/#28c840] [#ffffff]{written}[/#ffffff] documents -> [#ffffff]{output}[/#ffffff]")

@app.command(name="validate")
def validate_command(
    target: Path = typer.Argument(..., help="File or folder to validate"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subdirectories"),
    chunk_strategy: str = typer.Option("recursive", "--chunk-strategy", help="Chunk strategy: recursive, paragraph, sentence, token")
) -> None:
    """Validate extraction quality without moving files or updating ingest state."""
    setup_logging()
    if not target.exists():
        console.print(f"  [bold red]Error:[/bold red] Target does not exist: {target}")
        raise typer.Exit(1)

    from src.pipeline.ingest import Ingestor
    from src.state_manager import StateManager

    with tempfile.TemporaryDirectory() as temp_dir:
        ingestor = Ingestor(
            state_manager=StateManager(Path(temp_dir) / "state.db"),
            chunk_strategy=chunk_strategy,
            use_state=False,
        )
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
    index_status = None
    try:
        from src.search import inspect_index_dir
        index_status = inspect_index_dir()
    except Exception:
        index_status = None

    console.print("\n  [#444444]FORGE DOCTOR[/#444444]\n")
    for label, available in checks:
        status = "[#28c840]ok[/#28c840]" if available else "[#febc2e]missing[/#febc2e]"
        console.print(f"  [#e8550a]›[/#e8550a] [#888888]{label}:[/#888888] {status}")
    console.print(f"\n  [#e8550a]›[/#e8550a] [#888888]search index:[/#888888] [#ffffff]{search_index.resolve()}[/#ffffff]")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]state db:[/#888888]     [#ffffff]{state_db}[/#ffffff]")
    if index_status:
        console.print(f"  [#e8550a]›[/#e8550a] [#888888]vectors:[/#888888]      [#ffffff]{index_status['vector_count']}[/#ffffff]")
        console.print(f"  [#e8550a]›[/#e8550a] [#888888]metadata:[/#888888]     [#ffffff]{index_status['metadata_count']}[/#ffffff]")
        console.print(f"  [#e8550a]›[/#e8550a] [#888888]chunk records:[/#888888] [#ffffff]{index_status['chunk_records']}[/#ffffff]")
        console.print(f"  [#e8550a]›[/#e8550a] [#888888]legacy records:[/#888888] [#ffffff]{index_status['legacy_records']}[/#ffffff]")
        console.print(f"  [#e8550a]›[/#e8550a] [#888888]counts match:[/#888888] [#ffffff]{index_status['counts_match']}[/#ffffff]")
    console.print("")

@app.command(name="clean")
def clean_command(
    target: Path = typer.Argument(..., help="File or folder to inspect"),
    dupes: bool = typer.Option(False, "--dupes", help="Report duplicate extracted documents"),
    semantic: bool = typer.Option(False, "--semantic", help="Use embedding similarity for near-duplicate reporting"),
    threshold: float = typer.Option(0.97, "--threshold", help="Semantic duplicate cosine threshold"),
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

    from src.intelligence.dedup import dedup_documents, semantic_duplicate_clusters
    from src.pipeline.ingest import Ingestor
    from src.state_manager import StateManager

    with tempfile.TemporaryDirectory() as temp_dir:
        ingestor = Ingestor(state_manager=StateManager(Path(temp_dir) / "state.db"), use_state=False)
        docs = [doc for doc in ingestor.run(target.resolve(), recursive=recursive) if doc.content]

    if semantic:
        clusters = semantic_duplicate_clusters(docs, threshold=threshold)
        duplicate_count = sum(len(cluster.duplicates) for cluster in clusters)
    else:
        clusters = []
        deduped = dedup_documents(docs)
        duplicate_count = len(docs) - len(deduped)
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]documents scanned:[/#888888] [#ffffff]{len(docs)}[/#ffffff]")
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]duplicates found:[/#888888] [#ffffff]{duplicate_count}[/#ffffff]")
    for cluster in clusters[:10]:
        duplicate_names = ", ".join(doc.filename for doc in cluster.duplicates)
        console.print(f"    [#f5a623]keep[/#f5a623] {cluster.kept.filename} [#888888]<-[/#888888] {duplicate_names} [dim]({cluster.score:.2f})[/dim]")

@app.command(name="chunk")
def chunk_command(
    target: Path = typer.Argument(..., help="File or folder to chunk"),
    strategy: str = typer.Option("recursive", "--strategy", help="Chunk strategy: recursive, paragraph, sentence, token"),
    max_chars: int = typer.Option(1000, "--max-chars", help="Maximum characters per chunk"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subdirectories")
) -> None:
    """Preview chunk counts using a named chunking strategy."""
    setup_logging()
    if not target.exists():
        console.print(f"  [bold red]Error:[/bold red] Target does not exist: {target}")
        raise typer.Exit(1)

    from src.pipeline.ingest import Ingestor
    from src.state_manager import StateManager

    with tempfile.TemporaryDirectory() as temp_dir:
        ingestor = Ingestor(
            state_manager=StateManager(Path(temp_dir) / "state.db"),
            max_chunk_chars=max_chars,
            chunk_strategy=strategy,
            use_state=False,
        )
        docs = list(ingestor.run(target.resolve(), recursive=recursive))

    console.print(f"  [#e8550a]›[/#e8550a] [#888888]strategy:[/#888888] [#ffffff]{strategy}[/#ffffff]")
    for doc in docs:
        if doc.extraction_error:
            console.print(f"    [yellow]{doc.filename}[/yellow]: {doc.extraction_error}")
        else:
            console.print(f"    [#f5a623]{doc.filename}[/#f5a623]: [#ffffff]{len(doc.chunks)}[/#ffffff] chunks")

@app.command(name="export")
def export_command(
    target: Optional[Path] = typer.Argument(None, help="File or folder to export"),
    export_format: str = typer.Option("jsonl", "--format", "-f", help="jsonl, csv, markdown, parquet, or rag"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Export output path"),
    from_jsonl: Optional[Path] = typer.Option(None, "--from-jsonl", help="Export existing Document JSONL"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subdirectories"),
    chunk_strategy: str = typer.Option("recursive", "--chunk-strategy", help="Chunk strategy for folder export")
) -> None:
    """Export Document records to local files."""
    setup_logging()
    if target is None and from_jsonl is None:
        console.print("  [bold red]Error:[/bold red] Provide a file/folder or --from-jsonl.")
        raise typer.Exit(1)
    if target is not None and not target.exists():
        console.print(f"  [bold red]Error:[/bold red] Target does not exist: {target}")
        raise typer.Exit(1)
    if from_jsonl is not None and not from_jsonl.exists():
        console.print(f"  [bold red]Error:[/bold red] JSONL file does not exist: {from_jsonl}")
        raise typer.Exit(1)

    from src.exporters import export_documents, load_documents

    output_path = output or _default_export_output(export_format)
    try:
        documents = load_documents(
            target=target,
            from_jsonl=from_jsonl,
            recursive=recursive,
            chunk_strategy=chunk_strategy,
        )
        export_documents(documents, output_path, export_format)
    except Exception as e:
        console.print(f"  [bold red]Export failed:[/bold red] [red]{e}[/red]")
        raise typer.Exit(1)

    console.print(f"  [#e8550a]›[/#e8550a] [#28c840]Export complete:[/#28c840] [#ffffff]{len(documents)}[/#ffffff] documents -> [#ffffff]{output_path}[/#ffffff]")

@app.command(name="transform")
def transform_command(
    target: Optional[Path] = typer.Argument(None, help="File or folder to transform"),
    template: str = typer.Option(..., "--template", "-t", help="Template name"),
    output: Path = typer.Option(Path("transform.jsonl"), "--output", "-o", help="Transform output JSONL path"),
    from_jsonl: Optional[Path] = typer.Option(None, "--from-jsonl", help="Transform existing Document JSONL"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subdirectories"),
    chunk_strategy: str = typer.Option("recursive", "--chunk-strategy", help="Chunk strategy for folder transform"),
    local: bool = typer.Option(False, "--local", "-l", help="Run template prompt through local Ollama"),
    ollama_model: str = typer.Option("llama3.2", "--ollama-model", help="Ollama model for local transform")
) -> None:
    """Apply a local YAML template to Document records."""
    setup_logging()
    if target is None and from_jsonl is None:
        console.print("  [bold red]Error:[/bold red] Provide a file/folder or --from-jsonl.")
        raise typer.Exit(1)
    if target is not None and not target.exists():
        console.print(f"  [bold red]Error:[/bold red] Target does not exist: {target}")
        raise typer.Exit(1)
    if from_jsonl is not None and not from_jsonl.exists():
        console.print(f"  [bold red]Error:[/bold red] JSONL file does not exist: {from_jsonl}")
        raise typer.Exit(1)

    from src.exporters import load_documents
    from src.transform import TemplateEngine

    try:
        documents = load_documents(
            target=target,
            from_jsonl=from_jsonl,
            recursive=recursive,
            chunk_strategy=chunk_strategy,
        )
        engine = TemplateEngine()
        results = engine.transform(documents, template, use_ollama=local, model=ollama_model)
    except Exception as e:
        console.print(f"  [bold red]Transform failed:[/bold red] [red]{e}[/red]")
        raise typer.Exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(json.dumps(result, ensure_ascii=False) for result in results) + "\n",
        encoding="utf-8",
    )
    mode = "local Ollama" if local else "rendered prompts"
    console.print(f"  [#e8550a]›[/#e8550a] [#28c840]Transform complete:[/#28c840] [#ffffff]{len(results)}[/#ffffff] records ({mode}) -> [#ffffff]{output}[/#ffffff]")

@app.command(name="pack")
def pack_command(
    target: Optional[Path] = typer.Argument(None, help="File or folder to pack"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Context pack output path"),
    from_jsonl: Optional[Path] = typer.Option(None, "--from-jsonl", help="Pack existing Document JSONL"),
    pack_format: str = typer.Option("markdown", "--format", "-f", help="markdown or jsonl"),
    token_budget: int = typer.Option(8000, "--token-budget", help="Total context window budget"),
    reserve_tokens: int = typer.Option(500, "--reserve-tokens", help="Tokens to leave unused for instructions/answer"),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Prioritize chunks matching this task or question"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subdirectories"),
    chunk_strategy: str = typer.Option("recursive", "--chunk-strategy", help="Chunk strategy for folder packing")
) -> None:
    """Create a token-aware local context bundle for AI workflows."""
    setup_logging()
    if target is None and from_jsonl is None:
        console.print("  [bold red]Error:[/bold red] Provide a file/folder or --from-jsonl.")
        raise typer.Exit(1)
    if target is not None and not target.exists():
        console.print(f"  [bold red]Error:[/bold red] Target does not exist: {target}")
        raise typer.Exit(1)
    if from_jsonl is not None and not from_jsonl.exists():
        console.print(f"  [bold red]Error:[/bold red] JSONL file does not exist: {from_jsonl}")
        raise typer.Exit(1)

    from src.exporters import load_documents
    from src.pack import build_context_pack, write_context_pack

    output_path = output or _default_pack_output(pack_format)
    try:
        documents = load_documents(
            target=target,
            from_jsonl=from_jsonl,
            recursive=recursive,
            chunk_strategy=chunk_strategy,
        )
        pack = build_context_pack(
            documents,
            token_budget=token_budget,
            reserve_tokens=reserve_tokens,
            query=query,
        )
        write_context_pack(pack, output_path, pack_format)
    except Exception as e:
        console.print(f"  [bold red]Pack failed:[/bold red] [red]{e}[/red]")
        raise typer.Exit(1)

    console.print(
        f"  [#e8550a]›[/#e8550a] [#28c840]Pack complete:[/#28c840] "
        f"[#ffffff]{len(pack.entries)}[/#ffffff] chunks, "
        f"[#ffffff]{pack.estimated_tokens}/{pack.available_tokens}[/#ffffff] estimated tokens -> "
        f"[#ffffff]{output_path}[/#ffffff]"
    )

@app.command(name="dataset")
def dataset_command(
    target: Optional[Path] = typer.Argument(None, help="File or folder to turn into a dataset"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Dataset output path"),
    from_jsonl: Optional[Path] = typer.Option(None, "--from-jsonl", help="Build from existing Document JSONL"),
    dataset_format: str = typer.Option("jsonl", "--format", "-f", help="jsonl, csv, markdown, parquet, or rag"),
    dedup: bool = typer.Option(True, "--dedup/--no-dedup", help="Remove exact duplicate document content"),
    semantic: bool = typer.Option(False, "--semantic", help="Use optional local embeddings for near-duplicate removal"),
    threshold: float = typer.Option(0.97, "--threshold", help="Semantic duplicate cosine threshold"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subdirectories"),
    chunk_strategy: str = typer.Option("recursive", "--chunk-strategy", help="Chunk strategy for folder datasets"),
    manifest: bool = typer.Option(True, "--manifest/--no-manifest", help="Write a dataset manifest next to the output")
) -> None:
    """Build a cleaned, deduplicated local dataset export."""
    setup_logging()
    if target is None and from_jsonl is None:
        console.print("  [bold red]Error:[/bold red] Provide a file/folder or --from-jsonl.")
        raise typer.Exit(1)
    if target is not None and not target.exists():
        console.print(f"  [bold red]Error:[/bold red] Target does not exist: {target}")
        raise typer.Exit(1)
    if from_jsonl is not None and not from_jsonl.exists():
        console.print(f"  [bold red]Error:[/bold red] JSONL file does not exist: {from_jsonl}")
        raise typer.Exit(1)
    if semantic and not dedup:
        console.print("  [yellow]--semantic requires deduplication. Use --dedup or omit --no-dedup.[/yellow]")
        raise typer.Exit(1)

    from src.dataset import write_dataset
    from src.exporters import load_documents

    output_path = output or _default_dataset_output(dataset_format)
    try:
        documents = load_documents(
            target=target,
            from_jsonl=from_jsonl,
            recursive=recursive,
            chunk_strategy=chunk_strategy,
        )
        result = write_dataset(
            documents,
            output_path,
            export_format=dataset_format,
            dedup=dedup,
            semantic=semantic,
            threshold=threshold,
            write_manifest=manifest,
        )
    except Exception as e:
        console.print(f"  [bold red]Dataset failed:[/bold red] [red]{e}[/red]")
        raise typer.Exit(1)

    console.print(
        f"  [#e8550a]›[/#e8550a] [#28c840]Dataset complete:[/#28c840] "
        f"[#ffffff]{result.output_count}[/#ffffff] documents -> [#ffffff]{output_path}[/#ffffff]"
    )
    console.print(
        f"  [#e8550a]›[/#e8550a] [#888888]duplicates removed:[/#888888] "
        f"[#ffffff]{result.duplicate_count}[/#ffffff]  "
        f"[#888888]extraction errors skipped:[/#888888] [#ffffff]{result.skipped_error_count}[/#ffffff]"
    )

@template_app.command(name="list")
def template_list_command() -> None:
    """List installed local transform templates."""
    from src.transform import TemplateEngine

    engine = TemplateEngine()
    templates = engine.list_templates()
    if not templates:
        console.print("  [yellow]No templates found.[/yellow]")
        return
    for name in templates:
        console.print(f"  [#e8550a]›[/#e8550a] [#ffffff]{name}[/#ffffff]")

@app.command(name="index")
def index_command(
    target: Optional[Path] = typer.Argument(None, help="Folder to index"),
    from_jsonl: Optional[Path] = typer.Option(None, "--from-jsonl", help="Index existing Document JSONL"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Include subdirectories"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-e", help="Skip files"),
    chunk_strategy: str = typer.Option("recursive", "--chunk-strategy", help="Chunk strategy for folder indexing"),
    env: str = typer.Option("default", "--env", help="Environment config")
) -> None:
    """Index files for semantic search."""
    setup_logging()
    if target is None and from_jsonl is None:
        console.print("  [bold red]Error:[/bold red] Provide a folder or --from-jsonl.")
        raise typer.Exit(1)
    if from_jsonl is not None and not from_jsonl.exists():
        console.print(f"  [bold red]Error:[/bold red] JSONL file does not exist: {from_jsonl}")
        raise typer.Exit(1)
    if target is not None and not target.exists():
        console.print(f"  [bold red]Error:[/bold red] Target does not exist: {target}")
        raise typer.Exit(1)

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
        if from_jsonl is not None:
            indexed = searcher.build_index_from_jsonl(from_jsonl, progress)
        else:
            indexed = searcher.build_index(
                target,
                progress,
                recursive=recursive,
                exclude=exclude or [],
                chunk_strategy=chunk_strategy,
            )
    console.print(f"\n  [#28c840]Indexing complete.[/#28c840] [#ffffff]{indexed or 0}[/#ffffff] chunks indexed. You can now use 'forge search'.\n")

@app.command(name="search")
def search_command(
    query: str = typer.Argument(..., help="Natural language search query"),
    limit: int = typer.Option(3, "--limit", "-n", help="Number of results to return"),
    explain: bool = typer.Option(False, "--explain", help="Show dense, BM25, chunk, and matched-term details"),
    rerank: bool = typer.Option(False, "--rerank", help="Use optional local CrossEncoder reranking"),
    hyde: bool = typer.Option(False, "--hyde", help="Use local Ollama HyDE query rewriting"),
    local: bool = typer.Option(False, "--local", "-l", help="Allow local Ollama features"),
    ollama_model: str = typer.Option("llama3.2", "--ollama-model", help="Ollama model for local HyDE"),
    compress: bool = typer.Option(False, "--compress", help="Show compressed query-relevant snippets")
) -> None:
    """
    Search for files using natural language (e.g. 'tax forms from last year').
    """
    setup_logging()
    console.print(f"  [#e8550a]›[/#e8550a] [#888888]searching for:[/#888888] [#ffffff]\"{query}\"[/#ffffff]\n")
    
    try:
        from src.search import SemanticSearch
        search_query = None
        if hyde:
            if not local:
                console.print("  [yellow]HyDE requires --local so it can use local Ollama. Falling back to the raw query.[/yellow]")
            else:
                from src.llm import LocalLLM
                llm = LocalLLM(model=ollama_model, use_ollama=True)
                search_query = llm.hyde_query(query)
                if explain:
                    console.print(f"  [#e8550a]›[/#e8550a] [#888888]hyde query:[/#888888] [#ffffff]{search_query}[/#ffffff]\n")
        searcher = SemanticSearch()
        results = searcher.search(
            query,
            limit,
            rerank=rerank,
            compress=compress,
            search_query=search_query,
        )
        
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
            if metadata.get("index_level") == "chunk":
                console.print(f"    [#5bc8f5]Chunk:[/#5bc8f5] [#ffffff]{metadata.get('chunk_index', 0) + 1}/{metadata.get('chunk_count', '?')}[/#ffffff]")
            if explain:
                dense = metadata.get("_dense_score", 0.0)
                bm25 = metadata.get("_bm25_score", 0.0)
                terms = ", ".join(metadata.get("_matched_terms", [])) or "none"
                tags = ", ".join(metadata.get("tags", [])) or "none"
                console.print(f"    [#888888]dense:[/#888888] {dense:.2f}  [#888888]bm25:[/#888888] {bm25:.2f}  [#888888]matched:[/#888888] {terms}")
                if "_rerank_score" in metadata:
                    console.print(f"    [#888888]rerank:[/#888888] {metadata['_rerank_score']:.2f}")
                console.print(f"    [#888888]tags:[/#888888] {tags}")
            snippet_panel = Panel(
                Text(f"\"{metadata.get('_compressed_snippet') or metadata['snippet']}\"", style="dim"),
                border_style="dim",
                padding=(0, 1)
            )
            console.print(snippet_panel)
            console.print("\n") 
            
    except Exception as e:
        console.print(f"  [bold red]Search failed:[/bold red] [red]{e}[/red]")

if __name__ == "__main__":
    app()
