# File Organizer API Documentation

## Modules

### `src.classifier`
Handles determining file categories based on extensions.

*   `get_category(extension: str, categories: Dict[str, List[str]]) -> str`
    Determines the matching category for a file extension. Returns `'Misc'` as fallback.
*   `get_destination_path(file: Path, destination: Path, categories: Dict[str, List[str]], date_sort: bool = False) -> Path`
    Constructs the final target path for the file, handling optional date-based subfolders.

### `src.config_loader`
Manages the application configuration and category JSON loading.

*   `load_all_configs(env: str = "default") -> Tuple[Dict[str, Any], Dict[str, List[str]]]`
    Loads both `config.json` and `categories.json`, validating their structure and returning them.

### `src.logger`
Configures application logging.

*   `setup_logging() -> None`
    Sets up file logging inside the `logs/` directory.

### `src.organizer`
Contains the core execution logic.

*   `organize(target: Path, destination: Path, dry_run: bool, recursive: bool, exclude: List[str], categories: Dict[str, List[str]], date_sort: bool = False, copy_mode: bool = False) -> None`
    Orchestrates scanning, copying/moving files, rendering rich progress bars, and saving history logs.

### `src.utils`
Utility and history functions.

*   `collect_files(target: Path, recursive: bool) -> List[Path]`
    Yields all file paths in a target directory.
*   `resolve_collision(destination: Path) -> Path`
    Adds an incremental counter to filenames (e.g. `_1`) if a file already exists at the destination.
*   `undo_last() -> None`
    Uses the latest transaction JSON in `history/` to cleanly revert the previous file operations.
