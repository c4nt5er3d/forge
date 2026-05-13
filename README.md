# F.O.R.G.E.

[![CI](https://github.com/c4nt5er3d/forge/actions/workflows/test.yml/badge.svg)](https://github.com/c4nt5er3d/forge/actions/workflows/test.yml)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)
![Version](https://img.shields.io/badge/version-0.2.0-purple)
![Lint](https://img.shields.io/badge/lint-ruff-FCC21B?logo=ruff&logoColor=black)
![License](https://img.shields.io/badge/license-MIT-green)

**FORGE is a local-first document intelligence engine for turning messy files into searchable, structured, AI-ready context.**

It still does safe file organization, previews, smart renames, and undo, but the core 0.2.0 workflow is broader: ingest folders, extract clean `Document` JSONL, chunk and index content, search locally, export datasets, build context packs, evaluate retrieval, and expose everything through local HTTP or MCP.

```bash
git clone https://github.com/c4nt5er3d/forge
cd forge
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
forge
```

## Start Here

**Organize files safely**

```bash
forge organize ~/Downloads organized --preview
forge organize ~/Downloads organized
forge undo --preview
```

**Build a local document index**

```bash
forge ingest docs --output docs.jsonl --recursive
forge index --from-jsonl docs.jsonl
forge search "budget approvals" --explain
```

**Prepare context for AI tools**

```bash
forge pack --from-jsonl docs.jsonl --query "release planning" --output context_pack.md
forge dataset --from-jsonl docs.jsonl --output dataset.jsonl
forge evaluate eval_cases.json --output evaluation.json
```

## Command Map

**Organize files**

```bash
forge organize <source> <destination> --preview
forge copy <source> <destination>
forge rename <folder> --preview
forge watch <source> <destination>
```

**Build document intelligence**

```bash
forge ingest <folder> --output docs.jsonl --recursive
forge validate <folder> --recursive
forge chunk <folder> --strategy paragraph|sentence|token|recursive
forge clean <folder> --dupes --semantic --threshold 0.97
```

**Search and retrieve**

```bash
forge index <folder>
forge index --from-jsonl docs.jsonl
forge search "tax forms from last year" --explain
forge search "tax forms from last year" --rerank --compress
forge search "tax forms from last year" --hyde --local
```

**Package and evaluate context**

```bash
forge export --from-jsonl docs.jsonl --format rag --output rag_bundle
forge template list
forge transform --from-jsonl docs.jsonl --template summary --output summary.jsonl
forge pack --from-jsonl docs.jsonl --token-budget 8000 --output context_pack.md
forge dataset --from-jsonl docs.jsonl --format jsonl --output dataset.jsonl
forge evaluate eval_cases.json --format markdown --output evaluation.md
```

**Integrate locally**

```bash
forge serve --allow-root /path/to/workspace
forge mcp --allow-root /path/to/workspace
forge doctor
```

## What Changed in 0.2.0

- **Document pipeline**: `ingest`, `validate`, chunking strategies, quality scores, cleaning logs, and SQLite-backed ingest state.
- **Search intelligence**: chunk-level FAISS indexing, hybrid dense/BM25 scoring, explain output, reranking, HyDE, and deterministic compression.
- **Data products**: JSONL/CSV/Markdown/RAG exports, YAML templates, context packs, dataset builds, and retrieval evaluation.
- **Local integrations**: optional localhost HTTP API and MCP stdio adapter.
- **Still local-first**: no cloud service or API key is required for core workflows.

## Optional Installs

Install only what you need:

```bash
python -m pip install -e ".[ml]"      # TF-IDF classifier training
python -m pip install -e ".[ai]"      # embeddings, FAISS, OCR, Ollama helpers
python -m pip install -e ".[server]"  # forge serve
python -m pip install -e ".[mcp]"     # forge mcp
python -m pip install -e ".[full]"    # all optional runtime features
python -m pip install -e ".[dev]"     # tests, lint, and all optional features
```

## Pipeline Notes

`forge ingest` emits one JSON object per line using the stable `Document` contract: source metadata, extracted content, chunks, quality score, cleaning log, tags, and explicit `extraction_error` values when a file cannot produce usable text.

`forge index` can build from folders or existing JSONL and indexes chunks with metadata for document ID, chunk ID, tags, quality score, and chunk strategy. FAISS remains the local search backend; ChromaDB is intentionally deferred until upsert/delete behavior becomes painful.

`forge pack`, `forge dataset`, and `forge evaluate` are composed local workflows on top of the same document records. They do not call cloud APIs.

## Local API and MCP

`forge serve` starts a localhost API with:

- `GET /health`
- `POST /search`
- `POST /pack`
- `POST /dataset`
- `POST /evaluate`

`forge mcp` exposes the same service layer as MCP tools:

- `forge_health`
- `forge_search`
- `forge_pack`
- `forge_dataset`
- `forge_evaluate`

Example MCP client command:

```json
{
  "command": "forge",
  "args": ["mcp", "--allow-root", "/path/to/workspace"]
}
```

## Demo

Use the committed demo fixtures for a deterministic organizer walkthrough:

```bash
python demo/setup_demo_data.py
forge organize demo/messy demo/organized --preview
forge organize demo/messy demo/organized
forge undo --preview
forge undo --steps 1
```

![FORGE Preview](docs/demo/forge-preview.png)

![FORGE Organize](docs/demo/forge-organize.png)

![FORGE Undo](docs/demo/forge-undo.png)

![FORGE Demo GIF](docs/demo/forge-demo.gif)

## Safety Guarantees

- Preview mode is non-mutating.
- Undo history is written for move/copy operations.
- File collisions are resolved before writing.
- Hidden files and `.git` internals are skipped.
- Smart rename prefers skipping over producing low-confidence or artifact-based names.
- Server and MCP paths are restricted by `--allow-root`.

## Troubleshooting

**`forge` command not found**

```bash
python -m pip install -e ".[dev]"
forge --help
```

**Tesseract OCR not working for images**

```bash
python -m pip install -e ".[ai]"
tesseract --version
```

If `tesseract` is missing, install the system binary:

- macOS: `brew install tesseract`
- Ubuntu/Debian: `sudo apt-get update && sudo apt-get install -y tesseract-ocr`

**Ollama local mode unavailable**

```bash
ollama --version
ollama serve
ollama pull llama3.2
forge rename <folder> --local
```

**Semantic search returns no results**

```bash
python -m pip install -e ".[ai]"
forge index <folder>
forge search "project notes"
```

**Server or MCP command asks for optional dependencies**

```bash
python -m pip install -e ".[server]"
python -m pip install -e ".[mcp]"
```

## Development

```bash
python -m pip install -e ".[dev]"
python3 -m ruff check src tests
python -m pytest tests/
```

## Release Notes

- Changelog: [CHANGELOG.md](CHANGELOG.md)
- 0.2.0 release notes: [RELEASE_NOTES_0.2.0.md](RELEASE_NOTES_0.2.0.md)
- 0.1.0 release notes: [RELEASE_NOTES_0.1.0.md](RELEASE_NOTES_0.1.0.md)

## Final Fresh-Clone Test

```bash
git clone https://github.com/c4nt5er3d/forge
cd forge
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
forge --help
python3 -m ruff check src tests
python -m pytest tests/
python demo/setup_demo_data.py
forge organize demo/messy demo/organized --preview
```

Current version: **0.2.0**
