# File Organizer API Documentation

## CLI

Public commands use positional paths:

* `forge organize <target> [destination] [--preview] [--recursive] [--exclude EXT] [--date-sort] [--smart] [--local]`
* `forge copy <source> <destination> [--preview] [--recursive] [--exclude EXT] [--date-sort]`
* `forge rename <target> [--preview] [--recursive] [--exclude EXT] [--smart] [--local]`
* `forge watch <target> [destination] [--recursive] [--exclude EXT] [--date-sort]`
* `forge index <target> [--recursive] [--exclude EXT]`
* `forge search "<query>" [--limit N]`
* `forge undo [--preview] [--steps N]`

The hidden `forge run` command remains available for older option-style scripts.

## Modules

### `src.classifier`
Handles determining file categories based on extension rules, optional ML predictions, and optional AI category overrides.

* `get_category(extension: str, categories: Dict[str, List[str]]) -> str`
  Determines the matching category for a file extension. Returns `Misc` as fallback.
* `get_destination_path(file: Path, destination: Path, categories: Dict[str, List[str]], date_sort: bool = False, ml_classifier: Any = None, override_category: Optional[str] = None, dest_name: Optional[str] = None) -> Path`
  Constructs the final target path, including optional date folders and optional renamed filename.

### `src.config_loader`
Loads JSON config and category mappings.

* `load_all_configs(env: str = "default") -> Tuple[Dict[str, Any], Dict[str, List[str]]]`
  Loads `config/config.json` plus category mappings, with environment-specific config override support.

### `src.organizer`
Contains the core file operation pipeline.

* `organize(target: Path, destination: Path, dry_run: bool, recursive: bool, exclude: List[str], categories: Dict[str, List[str]], date_sort: bool = False, copy_mode: bool = False, use_ai: bool = False, ai_rename: bool = False, rename_only: bool = False, use_ollama: bool = False) -> None`
  Scans files, applies deterministic/ML/AI categorization, optionally quality-gated smart renaming, resolves collisions, performs move/copy/rename, and saves transaction history.

### `src.llm`
Provides local text extraction and smart naming helpers.

* `extract_text(file_path: Path, max_chars: int = 2000) -> str`
  Extracts usable natural-language text from supported files. Unsupported, unreadable, or artifact-heavy files return an empty string.
* `LocalLLM.analyze_and_rename(file_path: Path, categories: List[str]) -> Tuple[Optional[str], Optional[str]]`
  Returns an optional category and safe filename. Low-confidence local renames return `(None, None)` so the original file stays unchanged.

### `src.search`
Builds and queries the semantic search index.

* `SemanticSearch.build_index(target_dir: Path, progress: Optional[Progress] = None, recursive: bool = True, exclude: Optional[List[str]] = None) -> None`
  Extracts usable text, embeds it, and stores FAISS index metadata when AI search dependencies are installed.

### `src.utils`
Utility and transaction history functions.

* `collect_files(target: Path, recursive: bool) -> List[Path]`
  Collects files from a target directory.
* `resolve_collision(destination: Path) -> Path`
  Adds an incremental suffix, such as `_1`, when a destination already exists.
* `undo_last(preview: bool = False, steps: int = 1, history_dir: Optional[Path] = None) -> None`
  Previews or reverts the latest active transaction logs.

## Logging

The current CLI writes timestamped logs to the repository-local `logs/` directory via `src.log_utils.setup_logging()`.
