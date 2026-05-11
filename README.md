# F.O.R.G.E.

**F.O.R.G.E. is a local-first CLI that safely previews, organizes, renames, searches, and undoes filesystem cleanup.**

It is built for messy folders like Downloads: inspect what will happen, move or copy files into useful categories, rename documents when the content is trustworthy, and undo the operation if you do not like the result.

## Quickstart

```bash
git clone <your-repo-url>
cd file_organizer
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
forge --help
```

First safe command:

```bash
forge organize ~/Downloads organized --preview
```

Nothing moves in preview mode. When the plan looks right:

```bash
forge organize ~/Downloads organized
```

Undo is built in:

```bash
forge undo --preview
forge undo --steps 1
```

## Demo

Demo assets are intentionally kept out of the repository until recorded. Use this workflow for the portfolio GIF or screenshots:

```bash
mkdir -p demo/messy demo/organized
touch demo/messy/invoice.pdf demo/messy/vacation.jpg demo/messy/archive.zip demo/messy/script.py
forge organize demo/messy demo/organized --preview
forge organize demo/messy demo/organized
forge undo --preview
forge undo --steps 1
```

Suggested final assets:

```text
docs/demo/forge-preview.png
docs/demo/forge-organize.png
docs/demo/forge-undo.png
docs/demo/forge-demo.gif
```

## Features

- **Safe preview**: See planned moves, copies, or renames before touching files.
- **Undo support**: Revert recent move/copy transactions from local history.
- **Collision handling**: Existing files are protected with numbered filenames like `report_1.pdf`.
- **Smart organize**: Categorize by extension rules, optional ML model, or optional local AI.
- **Smart rename**: Rename from trustworthy extracted text; noisy, empty, binary, and unsupported files stay unchanged.
- **Semantic search**: Optional vector search for natural-language file lookup.
- **Local-first design**: Core commands run locally without cloud APIs.

## Common Commands

```bash
# Move files into category folders
forge organize <source_folder> <destination_folder>

# Preview without changing files
forge organize <source_folder> <destination_folder> --preview

# Copy instead of move
forge copy <source_folder> <destination_folder>

# Rename files in place using quality-gated local extraction
forge rename <folder> --preview

# Monitor a folder for new files
forge watch <source_folder> <destination_folder>

# Build and query semantic search index
forge index <folder>
forge search "tax forms from last year"
```

## Optional AI

The core workflow does not require AI dependencies.

Install optional groups only when you need them:

```bash
python -m pip install -e ".[ml]"
python -m pip install -e ".[ai]"
python -m pip install -e ".[full]"
```

- **Tesseract OCR** improves text extraction from images for smart rename/search. If Tesseract is missing or an image has no readable text, FORGE skips the rename instead of inventing a bad filename.
- **Ollama** enables local LLM-assisted rename/category suggestions with `forge rename <folder> --local`.
- **Sentence Transformers + FAISS** power semantic search with `forge index` and `forge search`.

## Safety Guarantees

- Preview mode is non-mutating.
- Undo history is written for move/copy operations.
- File collisions are resolved before writing.
- Hidden files and `.git` internals are skipped.
- Smart rename prefers skipping over producing low-confidence or artifact-based names.

## Troubleshooting

**`forge` command not found**

Run the editable install from the project root:

```bash
python -m pip install -e ".[dev]"
```

**Tesseract is missing**

Core commands still work. Install Tesseract only if you need OCR-based image text extraction.

**Ollama is unavailable**

Use normal `forge rename <folder>` for local quality-gated keyword naming, or install/start Ollama before using `--local`.

**Semantic search returns no results**

Install AI dependencies, build the index, then search:

```bash
python -m pip install -e ".[ai]"
forge index <folder>
forge search "project notes"
```

**Permission errors**

Run against folders your user owns, or choose a writable destination. Preview mode is the safest first check.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/
```

Current version: **0.1.0**

## License

MIT. See [LICENSE](LICENSE).
