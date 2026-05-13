# Release Notes - 0.2.0

## Highlights

- FORGE is now a local-first document intelligence engine, not only a file organizer.
- New pipeline commands turn local files into structured `Document` JSONL with chunks, quality metadata, tags, and explicit extraction errors.
- Search now supports chunk-level indexing, hybrid dense/BM25 retrieval, explain output, reranking, HyDE query expansion, and deterministic context compression.
- New context/data workflows make local AI preparation practical: export, transform, pack, dataset, and evaluate.
- New local integration surfaces expose Forge through a localhost HTTP API and an MCP stdio server.

## New Commands

- `forge ingest`
- `forge validate`
- `forge doctor`
- `forge chunk`
- `forge clean --dupes`
- `forge export`
- `forge transform`
- `forge template list`
- `forge pack`
- `forge dataset`
- `forge evaluate`
- `forge serve`
- `forge mcp`

## Pipeline and Search

- Added a stable `Document` JSONL contract for local file intelligence.
- Added configurable chunking strategies: `recursive`, `paragraph`, `sentence`, and `token`.
- Added SQLite-backed ingest state for unchanged-file skips.
- Added normalization, enrichment, quality scoring, cleaning logs, tags, and SHA-256 metadata.
- Moved search toward chunk-level retrieval with persisted embeddings in metadata.
- Added hybrid local retrieval by fusing FAISS dense scores with BM25-style lexical scores.
- Added `--explain`, `--rerank`, `--hyde --local`, and `--compress` search modes.

## Data and Context Workflows

- Added exporters for JSONL, CSV, Markdown, optional Parquet, and RAG bundles.
- Added YAML transform templates with built-in `summary` and `flashcards`.
- Added token-aware context packs for AI workflows.
- Added dataset building with extraction-error filtering and exact or optional semantic deduplication.
- Added retrieval evaluation reports with hit rate and mean reciprocal rank.

## Local Integrations

- Added `forge serve` with endpoints for health, search, pack, dataset, and evaluate.
- Added `forge mcp` with tools: `forge_health`, `forge_search`, `forge_pack`, `forge_dataset`, and `forge_evaluate`.
- Both integration surfaces reuse the same local `ForgeService` path allow-root checks.

## Optional Extras

```bash
python -m pip install -e ".[ml]"      # classifier training
python -m pip install -e ".[ai]"      # embeddings, FAISS, OCR, Ollama helpers
python -m pip install -e ".[server]"  # localhost HTTP API
python -m pip install -e ".[mcp]"     # MCP stdio server
python -m pip install -e ".[full]"    # all optional runtime features
python -m pip install -e ".[dev]"     # tests, lint, and optional features
```

## Compatibility Notes

- Core organize/copy/rename/undo workflows remain local and continue to work without AI dependencies.
- Ollama features remain opt-in through explicit local flags such as `--local`.
- ChromaDB is still deferred; FAISS remains the local vector backend.
- Server and MCP commands require optional extras and should be bound to local, trusted roots with `--allow-root`.

## Validation Checklist Used

- `pytest -q`
- `python3 -m ruff check src tests`
- `git diff --check`
- `env PYTHONPYCACHEPREFIX=/private/tmp/forge_pycache python3 -m compileall -q src tests`
