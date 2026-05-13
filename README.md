# F.O.R.G.E.

[![CI](https://github.com/c4nt5er3d/forge/actions/workflows/test.yml/badge.svg)](https://github.com/c4nt5er3d/forge/actions/workflows/test.yml)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)
![Version](https://img.shields.io/badge/version-0.1.0-purple)
![Lint](https://img.shields.io/badge/lint-ruff-FCC21B?logo=ruff&logoColor=black)
![License](https://img.shields.io/badge/license-MIT-green)

**F.O.R.G.E. is a local-first CLI that safely previews, organizes, renames, searches, and undoes filesystem cleanup.**

It is built for messy folders like Downloads: inspect what will happen, move or copy files into useful categories, rename documents when the content is trustworthy, and undo the operation if you do not like the result.

FORGE also includes an early document pipeline: `forge ingest` extracts local files into a machine-readable `Document` JSONL contract without moving the originals.

> Note: This project started as a simple file organizer script, but it turned into this somehow.

```bash
git clone https://github.com/c4nt5er3d/forge
cd forge
python -m venv .venv
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

Use the committed demo fixtures and these commands to record a deterministic portfolio run:

```bash
python demo/setup_demo_data.py
forge organize demo/messy demo/organized --preview
forge organize demo/messy demo/organized
forge undo --preview
forge undo --steps 1
```

Expected media paths:

```text
docs/demo/forge-preview.png
docs/demo/forge-organize.png
docs/demo/forge-undo.png
docs/demo/forge-demo.gif
```


![FORGE Preview](docs/demo/forge-preview.png)

![FORGE Organize](docs/demo/forge-organize.png)

![FORGE Undo](docs/demo/forge-undo.png)

![FORGE Demo GIF](docs/demo/forge-demo.gif)

## Features

- **Safe preview**: See planned moves, copies, or renames before touching files.
- **Undo support**: Revert recent move/copy transactions from local history.
- **Collision handling**: Existing files are protected with numbered filenames like `report_1.pdf`.
- **Smart organize**: Categorize by extension rules, optional ML model, or optional local AI.
- **Smart rename**: Rename from trustworthy extracted text; noisy, empty, binary, and unsupported files stay unchanged.
- **Semantic search**: Optional vector search for natural-language file lookup.
- **Document ingest**: Extract files into JSONL `Document` records with chunks, quality scores, and explicit extraction errors.
- **Hybrid retrieval**: Search fuses FAISS dense retrieval with BM25-style lexical matching.
- **Context packs**: Build token-aware local bundles for AI prompts from folders or existing JSONL.
- **Dataset builds**: Compose ingest, chunking, deduplication, and export into one local command.
- **Retrieval evaluation**: Score local search quality with JSON/JSONL benchmark cases.
- **Local HTTP API**: Serve search, pack, dataset, and evaluation workflows on localhost.
- **Validation and doctor checks**: Inspect extraction issues and local dependency/index health.
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
forge index --from-jsonl docs.jsonl
forge search "tax forms from last year"
forge search "tax forms from last year" --explain
forge search "tax forms from last year" --rerank --explain
forge search "tax forms from last year" --compress
forge search "tax forms from last year" --hyde --local --explain

# Extract files into Document JSONL without moving originals
forge ingest <folder> --output output.jsonl --recursive
forge ingest <folder> --chunk-strategy sentence --output output.jsonl

# Check extraction health and local optional dependencies
forge validate <folder> --recursive
forge doctor

# Preview chunking without writing JSONL
forge chunk <folder> --strategy paragraph|sentence|token|recursive

# Report duplicate extracted documents without deleting files
forge clean <folder> --dupes --recursive
forge clean <folder> --dupes --semantic --threshold 0.97

# Export Document records
forge export <folder> --format jsonl --output docs.jsonl --recursive
forge export --from-jsonl docs.jsonl --format markdown --output docs.md
forge export --from-jsonl docs.jsonl --format rag --output rag_bundle

# Create a token-aware AI context bundle
forge pack <folder> --output context_pack.md --token-budget 8000 --recursive
forge pack --from-jsonl docs.jsonl --query "budget approvals" --output context_pack.md
forge pack --from-jsonl docs.jsonl --format jsonl --output context_pack.jsonl

# Build cleaned local datasets
forge dataset <folder> --output dataset.jsonl --recursive
forge dataset <folder> --format rag --output dataset_bundle --dedup
forge dataset --from-jsonl docs.jsonl --format markdown --output dataset.md

# Evaluate retrieval quality
forge evaluate eval_cases.json --output evaluation.json --limit 5
forge evaluate eval_cases.jsonl --format markdown --output evaluation.md

# Start local HTTP API
forge serve --allow-root /path/to/workspace

# Apply local YAML templates
forge template list
forge transform --from-jsonl docs.jsonl --template summary --output summary.jsonl
forge transform <folder> --template flashcards --local --output flashcards.jsonl
```

## Document Pipeline

`forge ingest` is the Phase 1 pipeline foundation. It emits one JSON object per line with stable file metadata, extracted content, chunks, a quality score, a cleaning log, and an explicit `extraction_error` when a file cannot produce usable text.

The pipeline is additive: it does not replace `organize`, `rename`, `watch`, `index`, or `search`. `forge ingest`, `forge validate`, and `forge index` support configurable chunking strategies: `recursive`, `paragraph`, `sentence`, and `token`. `forge index` uses the ingest pipeline and indexes document chunks with metadata such as document ID, chunk ID, tags, quality score, and chunk strategy. FAISS remains the semantic search backend for now; search fuses dense results with BM25-style lexical scores. ChromaDB is intentionally deferred until chunk-level upsert/delete behavior is needed.

Optional Phase 2 intelligence features stay local-first: `forge clean --dupes --semantic` uses local embeddings for near-duplicate reports, `forge search --rerank` uses a local CrossEncoder when the model is available, and `forge search --hyde --local` uses local Ollama to rewrite a query before retrieval. `forge search --compress` trims snippets down to the most query-relevant sentences without any model call.

## Export and Templates

`forge export` writes Document records to local formats: JSONL, CSV, Markdown, optional Parquet, or a small RAG bundle directory with `documents.jsonl` and `manifest.json`.

`forge transform` applies YAML templates from built-in templates or `~/.forge/templates`. By default it renders prompts locally without calling a model. Add `--local` to run the rendered prompt through local Ollama. No cloud API is used by the core transform engine.

## Context Packs

`forge pack` builds a local, token-aware context bundle for AI workflows. It accepts a file/folder or existing Document JSONL, skips extraction failures, estimates tokens without a cloud tokenizer, and keeps output under the requested budget while reserving space for instructions and model output.

By default it writes Markdown with a JSON manifest, source list, and selected chunks. Add `--query` to prioritize chunks that match a task or question, or `--format jsonl` for machine-readable pack records.

## Datasets

`forge dataset` is a composed local workflow: ingest or load Document JSONL, drop extraction failures, optionally deduplicate, and export to JSONL, CSV, Markdown, optional Parquet, or a RAG bundle. It writes a small manifest next to the dataset by default.

Exact deduplication is enabled by default. Add `--no-dedup` to preserve every usable record, or `--semantic` to use optional local embeddings for near-duplicate removal.

## Evaluation

`forge evaluate` runs local search against JSON or JSONL benchmark cases and reports hit rate plus mean reciprocal rank. Each case needs a `query` and an `expected` object, such as `{"filename": "budget.txt"}`, `{"path": "budget"}`, `{"document_id": "..."}`, `{"chunk_id": "..."}`, or `{"contains": "payroll"}`.

Reports can be written as JSON or Markdown. Evaluation uses the local FAISS index; run `forge index` first.

## Local API

`forge serve` starts a localhost HTTP API for programmatic access to Forge workflows. It binds to `127.0.0.1` by default and only allows file paths under configured `--allow-root` directories. Install optional server dependencies first:

```bash
python3 -m pip install -e ".[server]"
```

Available endpoints:

- `GET /health`
- `POST /search`
- `POST /pack`
- `POST /dataset`
- `POST /evaluate`

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
- **Sentence Transformers + FAISS** power semantic search with `forge index` and `forge search`. `rank_bm25` improves lexical ranking when installed, with a local fallback scorer otherwise.

## Safety Guarantees

- Preview mode is non-mutating.
- Undo history is written for move/copy operations.
- File collisions are resolved before writing.
- Hidden files and `.git` internals are skipped.
- Smart rename prefers skipping over producing low-confidence or artifact-based names.

## Troubleshooting

**`forge` command not found**

Run editable install from project root:

```bash
python -m pip install -e ".[dev]"
forge --help
```

**Tesseract OCR not working for images**

FORGE still runs core organize/copy/undo commands without OCR, but image text extraction needs both Python packages and the system binary:

```bash
# Python deps
python -m pip install -e ".[ai]"

# Verify the system binary exists
tesseract --version
```

If `tesseract` is not found, install it (examples):

- macOS (Homebrew): `brew install tesseract`
- Ubuntu/Debian: `sudo apt-get update && sudo apt-get install -y tesseract-ocr`

**Ollama local mode unavailable**

Normal rename still works without Ollama (`forge rename <folder>`). `--local` needs the Ollama daemon and model:

```bash
ollama --version
ollama serve
ollama pull llama3.2
forge rename <folder> --local
```

If `ollama.chat` fails, check that `ollama serve` is running in another terminal and the model is pulled.

**Semantic search returns no results**

Install AI dependencies, build index, then query:

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
ruff check src demo
python -m pytest tests/
```

## Release Notes

- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Initial release notes: [RELEASE_NOTES_0.1.0.md](RELEASE_NOTES_0.1.0.md)

## Final Fresh-Clone Test

```bash
git clone https://github.com/c4nt5er3d/forge
cd forge
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
forge --help
ruff check src demo
python -m pytest tests/
python demo/setup_demo_data.py
forge organize demo/messy demo/organized --preview
```

Current version: **0.1.0**
