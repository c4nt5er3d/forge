# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Phase 1 document pipeline with `Document` JSONL schema, chunking, validation, and SQLite ingest state.
- New `forge ingest`, `forge validate`, and `forge doctor` commands.
- Explicit extraction errors for unsupported, empty, or low-quality files in pipeline output.

### Changed
- Semantic search metadata now persists normalized embeddings so clean index rebuilds do not re-encode every valid snippet.
- Search query embeddings are normalized before FAISS lookup for consistent cosine-style scoring.
- Text pipeline extraction attempts charset detection before reporting encoding failures.

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
