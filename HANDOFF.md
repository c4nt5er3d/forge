# FORGE Handoff

Last updated: 2026-05-13

Branch: `update-file-organizer`

## Current Status

FORGE has moved from a file organizer/search CLI into a local-first document intelligence pipeline.

The current branch includes:

- Phase 1 pipeline foundation
- Phase 1.5 pipeline-backed chunk indexing
- Phase 2 search intelligence
- Phase 2A configurable chunking
- Phase 2B semantic dedup
- Phase 2C reranking
- Phase 2D HyDE query rewriting
- Phase 2E context compression
- Phase 3A exporters
- Phase 3B YAML template transform engine
- Phase 3C token-aware context packs
- Phase 3D dataset command
- Evaluation layer: forge evaluate
- Serve layer: local HTTP API

The project remains local-first. Core behavior does not require cloud APIs or paid services.

## Local-First Rules

Keep these rules intact:

- Core commands must run locally.
- No cloud API should be required for ingest, validate, organize, index, search, export, or transform.
- Ollama features are optional and must require explicit local flags such as `--local`.
- Cloud extractors or hosted vector stores may exist later only as optional plugins.
- ChromaDB is still deferred until local FAISS metadata/upsert behavior becomes a real blocker.

Network may be used only for optional model acquisition, such as the first local download of a Sentence Transformers model.

## Git State

Recent commits on this branch:

```text
92c7886 Add exports and templates
18e6a35 Add hyde and context compression
55991c4 Add semantic dedup and reranking
1535650 Add configurable chunking
0e62b7d Add pipeline backed indexing
2fedb34 Add phase 2 search intelligence
32dfba4 Add pipeline foundation
```

Known local untracked file:

```text
Forge-System-Definition.md
```

That file was intentionally left untracked and untouched.

## Major Features

### Pipeline Ingest

Command:

```bash
forge ingest <file-or-folder> --output output.jsonl --recursive
```

What it does:

- Reads files without moving or renaming them.
- Produces one `Document` JSON object per line.
- Extracts text where possible.
- Records explicit extraction errors for unsupported, empty, or unreadable files.
- Adds chunks, quality score, cleaning log, tags, word count, chunk count, and SHA-256 metadata.
- Uses SQLite state to skip unchanged files when state is enabled.

Useful flags:

```bash
forge ingest folder --output docs.jsonl
forge ingest folder --output docs.jsonl --recursive
forge ingest folder --output docs.jsonl --state state.db
forge ingest folder --output docs.jsonl --chunk-strategy sentence
```

### Validation

Command:

```bash
forge validate <file-or-folder> --recursive
```

What it does:

- Runs the ingest pipeline read-only.
- Does not write JSONL.
- Does not update long-lived ingest state.
- Reports extraction issues.

### Chunking

Command:

```bash
forge chunk <file-or-folder> --strategy sentence --max-chars 500
```

Strategies:

- `recursive`
- `paragraph`
- `sentence`
- `token`

Markdown tables and fenced code blocks are preserved as atomic chunks.

### Indexing

Commands:

```bash
forge index <folder> --recursive
forge index <folder> --chunk-strategy sentence
forge index --from-jsonl docs.jsonl
```

What it does:

- Uses the ingest pipeline.
- Indexes chunks, not just whole files.
- Stores metadata for document ID, chunk ID, chunk index, tags, quality score, and chunk strategy.
- Uses local FAISS for vector search.
- Stores embeddings in metadata so clean rebuilds do not re-encode valid snippets.

### Search

Commands:

```bash
forge search "budget planning"
forge search "budget planning" --limit 5
forge search "budget planning" --explain
forge search "budget planning" --compress
forge search "budget planning" --rerank --explain
forge search "budget planning" --hyde --local --compress --explain
```

What it does:

- Fuses local FAISS dense retrieval with BM25-style lexical scoring.
- Supports explain output for dense score, BM25 score, matched terms, tags, and chunk details.
- Supports optional local CrossEncoder reranking with `--rerank`.
- Supports optional local Ollama HyDE query rewriting with `--hyde --local`.
- Supports local context compression with `--compress`.

HyDE:

- Uses local Ollama only when `--local` is passed.
- Generates a hypothetical answer/document and searches with that richer text.
- Falls back to the original query if Ollama is unavailable or fails.

Context compression:

- Does not call a model.
- Picks the most query-relevant sentences from the matched snippet.

### Duplicate Detection

Commands:

```bash
forge clean <folder> --dupes
forge clean <folder> --dupes --semantic --threshold 0.97
```

What it does:

- Exact dedup is default and fast.
- Semantic dedup uses local embeddings to report near-duplicate clusters.
- It is read-only and does not delete files.

### Training

Command:

```bash
forge train <organized-training-folder>
```

Expected training folder shape:

```text
train/
  Documents/
    file1.txt
  Images/
    image1.jpg
  Code/
    script.py
```

What it does:

- Trains a local TF-IDF + Naive Bayes classifier.
- Saves model to:

```text
models/classifier.joblib
```

- Reports files found, category counts, skipped files, and warnings for categories with very few examples.

### Exporters

Commands:

```bash
forge export <folder> --format jsonl --output docs.jsonl --recursive
forge export <folder> --format csv --output docs.csv --recursive
forge export <folder> --format markdown --output docs.md --recursive
forge export <folder> --format rag --output rag_bundle --recursive
forge export --from-jsonl docs.jsonl --format markdown --output docs.md
```

Supported formats:

- `jsonl`
- `csv`
- `markdown`
- `rag`
- `parquet` when `pyarrow` is installed

RAG bundle output:

```text
rag_bundle/
  documents.jsonl
  manifest.json
```

### Template Transform Engine

Commands:

```bash
forge template list
forge transform <folder> --template summary --output summary.jsonl
forge transform --from-jsonl docs.jsonl --template flashcards --output flashcards.jsonl
forge transform <folder> --template flashcards --local --output flashcards.jsonl
```

Built-in templates:

- `summary`
- `flashcards`

Template locations:

```text
src/transform/templates/
~/.forge/templates/
```

Default behavior:

- Renders prompts locally.
- Does not call a model.

With `--local`:

- Sends rendered prompt to local Ollama.
- No cloud API is used.

### Context Packs

Commands:

```bash
forge pack <folder> --output context_pack.md --token-budget 8000 --recursive
forge pack --from-jsonl docs.jsonl --query "budget approvals" --output context_pack.md
forge pack --from-jsonl docs.jsonl --format jsonl --output context_pack.jsonl
```

What it does:

- Builds local context bundles from a file, folder, or existing Document JSONL.
- Estimates tokens deterministically without a cloud tokenizer.
- Reserves configurable space for instructions/model output.
- Skips extraction failures and empty chunks.
- Writes Markdown by default with a JSON manifest, source list, and selected chunks.
- Supports `--query` to prioritize chunks relevant to a task or question.
- Supports machine-readable `jsonl` output.

### Dataset Builder

Commands:

```bash
forge dataset <folder> --output dataset.jsonl --recursive
forge dataset <folder> --format rag --output dataset_bundle --dedup
forge dataset --from-jsonl docs.jsonl --format markdown --output dataset.md
forge dataset --from-jsonl docs.jsonl --no-dedup --output full_dataset.jsonl
```

What it does:

- Composes the existing local pipeline instead of adding a separate extraction path.
- Loads from a file/folder or existing Document JSONL.
- Drops extraction failures from the final dataset.
- Runs exact content deduplication by default.
- Supports `--no-dedup` when every usable record should be preserved.
- Supports optional local semantic deduplication with `--semantic`.
- Exports through the existing exporter formats: `jsonl`, `csv`, `markdown`, `rag`, and optional `parquet`.
- Writes a dataset manifest by default unless `--no-manifest` is passed.

### Retrieval Evaluation

Commands:

```bash
forge evaluate eval_cases.json --output evaluation.json --limit 5
forge evaluate eval_cases.jsonl --format markdown --output evaluation.md
forge evaluate eval_cases.json --rerank --compress
```

Case formats:

```json
[
  {
    "id": "budget",
    "query": "budget planning approvals",
    "expected": {"filename": "budget.txt"}
  }
]
```

What it does:

- Runs local search against JSON or JSONL benchmark cases.
- Requires a local index built with `forge index`.
- Supports expected matches by `filename`, `path`, `document_id`, `chunk_id`, or `contains`.
- Computes hit count, hit rate, and mean reciprocal rank.
- Writes JSON reports by default or Markdown with `--format markdown`.
- Can evaluate reranked or compressed search behavior with `--rerank` and `--compress`.

### Local HTTP API

Command:

```bash
forge serve --host 127.0.0.1 --port 8765 --allow-root /path/to/workspace
```

Optional dependency install:

```bash
python3 -m pip install -e ".[server]"
```

Endpoints:

```text
GET  /health
POST /search
POST /pack
POST /dataset
POST /evaluate
```

What it does:

- Starts a localhost FastAPI app through `uvicorn`.
- Keeps server dependencies optional under the `server` extra.
- Uses a testable `ForgeService` layer so endpoint behavior is not trapped inside HTTP handlers.
- Restricts API file paths to configured `--allow-root` directories.
- Reuses existing search, pack, dataset, and evaluate modules.
- Does not expose cloud features or require API keys.

## Key Files

Pipeline:

```text
src/schema/document.py
src/pipeline/extract.py
src/pipeline/chunker.py
src/pipeline/validator.py
src/pipeline/ingest.py
src/state_manager.py
```

Search and intelligence:

```text
src/search.py
src/intelligence/normalizer.py
src/intelligence/enricher.py
src/intelligence/dedup.py
```

Export and transform:

```text
src/exporters/base.py
src/dataset.py
src/evaluate.py
src/pack.py
src/server.py
src/transform/engine.py
src/transform/templates/summary.yaml
src/transform/templates/flashcards.yaml
```

CLI:

```text
src/main.py
```

Tests:

```text
tests/test_pipeline.py
tests/test_ai_components.py
tests/test_intelligence.py
tests/test_integration.py
tests/test_export_transform.py
tests/test_dataset.py
tests/test_evaluate.py
tests/test_pack.py
tests/test_server.py
```

## Testing

Run:

```bash
pytest -q
git diff --check
env PYTHONPYCACHEPREFIX=/private/tmp/forge_pycache python3 -m compileall -q src tests
```

Known local issue:

```bash
python3 -m ruff check src tests
```

may fail if `ruff` is not installed in the current Python environment.

Latest verified test count:

```text
68 passed
```

## Dummy Test Data

Dummy files were created under:

```text
/Users/jay/Documents/testing/forge-test
```

Important subfolders:

```text
/Users/jay/Documents/testing/forge-test/source
/Users/jay/Documents/testing/forge-test/train
/Users/jay/Documents/testing/forge-test/watch
/Users/jay/Documents/testing/forge-test/output
```

Useful smoke commands:

```bash
forge validate /Users/jay/Documents/testing/forge-test/source --recursive

forge ingest /Users/jay/Documents/testing/forge-test/source \
  --output /Users/jay/Documents/testing/forge-test/out.jsonl \
  --recursive

forge chunk /Users/jay/Documents/testing/forge-test/source/structured.md \
  --strategy sentence \
  --max-chars 80

forge clean /Users/jay/Documents/testing/forge-test/source --dupes --recursive

forge export /Users/jay/Documents/testing/forge-test/source \
  --format markdown \
  --output /Users/jay/Documents/testing/forge-test/export.md \
  --recursive

forge template list

forge transform /Users/jay/Documents/testing/forge-test/source/budget.txt \
  --template summary \
  --output /Users/jay/Documents/testing/forge-test/summary-transform.jsonl
```

## Roadmap Position

Completed:

```text
Phase 1: Pipeline foundation
Phase 1.5: Pipeline-backed chunk indexing
Phase 2A: Configurable chunking
Phase 2B: Semantic dedup
Phase 2C: Reranking
Phase 2D: HyDE query rewrite
Phase 2E: Context compression
Phase 3A: Exporters
Phase 3B: Template transform engine
Phase 3C: Token-aware context packs
Phase 3D: Dataset command
Evaluation layer: forge evaluate
Serve layer: local HTTP API
```

Next likely roadmap items:

```text
MCP adapter
Later: ChromaDB migration if FAISS metadata/upsert becomes painful
Much later: Forge Brain / LoRA fine-tuning
```

## Important Design Notes

ChromaDB:

- Not implemented yet.
- Still intentionally deferred.
- Add it only when chunk-level upsert/delete, metadata filtering, or larger persistent index management becomes painful with FAISS.

Templates:

- Current transform engine is intentionally simple.
- It renders local prompts by default.
- `--local` is required before sending prompts to Ollama.

Search:

- Search currently uses the local FAISS index plus lexical BM25-style scoring.
- Reranking is optional.
- HyDE is optional.
- Compression is local and deterministic.

Exports:

- JSONL, CSV, Markdown, and RAG bundle are core.
- Parquet requires optional `pyarrow`.

## Suggested Next Work

1. Push latest commits if not already pushed.
2. Add MCP adapter on top of the `ForgeService` layer.
3. Consider ChromaDB only if FAISS metadata/upsert behavior becomes painful.
