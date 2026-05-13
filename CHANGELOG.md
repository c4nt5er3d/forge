# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Phase 1 document pipeline with `Document` JSONL schema, chunking, validation, and SQLite ingest state.
- New `forge ingest`, `forge validate`, and `forge doctor` commands.
- Explicit extraction errors for unsupported, empty, or low-quality files in pipeline output.
- Phase 2 local intelligence helpers for normalization, enrichment, and exact content deduplication.
- Hybrid semantic search with FAISS dense retrieval fused with BM25-style lexical scoring.
- Read-only `forge clean --dupes` duplicate report.
- Pipeline-backed chunk indexing for `forge index`.
- `forge index --from-jsonl` for indexing existing Document JSONL output.
- `forge search --explain` for dense score, BM25 score, matched terms, tags, and chunk details.
- `forge doctor` index diagnostics for vector/metadata count, chunk records, legacy records, and count mismatches.
- Configurable chunking strategies: `recursive`, `paragraph`, `sentence`, and `token`.
- `forge chunk` for previewing chunk counts without writing JSONL.
- Semantic duplicate reporting with `forge clean --dupes --semantic`.
- Optional local CrossEncoder reranking with `forge search --rerank`.

### Changed
- Semantic search metadata now persists normalized embeddings so clean index rebuilds do not re-encode every valid snippet.
- Search query embeddings are normalized before FAISS lookup for consistent cosine-style scoring.
- Text pipeline extraction attempts charset detection before reporting encoding failures.
- `forge ingest` now normalizes extracted text and adds basic enrichment metadata.
- `forge train` now reports category counts and warns when categories have very few examples.
- `forge ingest`, `forge validate`, and folder-based `forge index` accept chunk strategy options.

## [0.1.0] - 2026-05-11

### Added
- Local-first CLI workflow for organize/copy/rename/watch/index/search/undo commands.
- Demo fixture generator at `demo/setup_demo_data.py` for reproducible showcase recording.
- Ruff lint configuration and CI lint job integration.
- GitHub Actions matrix for Python 3.10, 3.11, and 3.12 with install smoke test.
- Troubleshooting guidance for Tesseract OCR and Ollama local LLM mode.
- Release documentation in `RELEASE_NOTES_0.1.0.md`.

### Changed
- README expanded with badges, demo placeholders, release links, and fresh-clone validation steps.
