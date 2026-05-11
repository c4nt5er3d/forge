# Release Notes - 0.1.0

## Highlights
- Launch of `forge`, a local-first file organizer CLI with preview-first safety.
- Built-in undo support for move/copy transactions.
- Smart rename flow that prefers skipping low-confidence text over risky filenames.
- Optional semantic search with local embeddings and FAISS.
- Optional local LLM support through Ollama (`--local`) for rename/category suggestions.

## Included in this release
- Core commands: `organize`, `copy`, `rename`, `watch`, `undo`, `train`, `index`, `search`.
- Developer workflow improvements:
  - Ruff linting support
  - CI install smoke test
  - Python CI matrix (3.10 / 3.11 / 3.12)
- Documentation improvements:
  - Demo setup and media placeholders
  - Tesseract and Ollama troubleshooting
  - Fresh-clone verification instructions

## Install
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
forge --help
```

## Optional AI dependencies
```bash
python -m pip install -e ".[ai]"
```

## Known limitations
- OCR-based rename/search requires a system-level Tesseract installation in addition to Python packages.
- `forge rename --local` requires Ollama running locally and an available model.
- Demo GIF/screenshots are intentionally user-recorded and not bundled as binary assets.

## Validation checklist used for this release
- Editable install smoke test: `forge --help`
- Lint: `ruff check src demo`
- Tests: `python -m pytest tests/`
- Demo flow smoke: `python demo/setup_demo_data.py` and preview organize command

