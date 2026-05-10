# F.O.R.G.E.
**File Organization & Retrieval Generation Engine** — An intelligent, AI-driven filesystem manager for the modern developer.

## Overview
F.O.R.G.E. is a local-first automation tool designed to solve the chaos of unorganized directories. Unlike simple extension-based sorters, it leverages Hybrid ML categorization and Local LLM (Ollama) analysis to understand file content, perform smart renaming, and enable semantic natural language search across your filesystem.

## Features
- **Smart Organize**: Sorts files into logical categories using a hybrid approach of deterministic extension rules and ML classification.
- **Real-Time Watchdog**: Monitors directories (like Downloads) and instantly organizes incoming files with debounce protection for stable I/O.
- **AI-Driven Renaming**: Uses local LLMs to generate descriptive, professional filenames based on actual file content or OCR data.
- **Semantic Search**: Natural language search (e.g., "tax forms from last year") using vector embeddings and L2 distance matching.
- **OCR Integration**: Automatically extracts text from images, receipts, and screenshots to inform categorization and search.
- **Transactional Undo**: Granular history tracking allows you to revert any batch operation with a single command.
- **First-Class Commands**: New native `copy`, `organize`, and `rename` commands for intuitive workflow control.

## Installation
```bash
# Clone the repo
git clone https://github.com/jay/forge.git

# Install core dependencies
pip install typer rich watchdog scikit-learn joblib

# Optional: Install AI/Search dependencies
pip install sentence-transformers faiss-cpu ollama pytesseract PyPDF2

# Run the project
forge --help
```

## Folder Structure
```text
/
├── config/         # JSON categories and user settings
├── history/        # Transaction logs for undo support
├── logs/           # Application execution logs
├── models/         # Trained ML classifier models
├── src/            # Core engine source code
│   ├── classifier.py     # Deterministic file matching logic
│   ├── config_loader.py  # Configuration environment loader
│   ├── llm.py            # Local LLM and OCR integration
│   ├── logger.py         # Silent file-based logging
│   ├── main.py           # CLI entrypoint and orchestration
│   ├── ml.py             # ML pipeline and training
│   ├── organizer.py      # Core execution pipeline
│   ├── search.py         # Vector search and indexing
│   ├── utils.py          # UI helpers and file utilities
│   └── watcher.py        # Real-time monitoring service
└── tests/          # Integration and performance tests
```

## Challenges & Lessons Learned
- **The "Download Stability" Problem**: Early versions tried to move files while they were still being downloaded by the browser. 
    - **Solution**: Implemented a debounced event handler that waits for the file size to remain stable for 3 seconds before processing.
- **LLM Performance Trade-offs**: Content analysis is expensive. 
    - **Solution**: Designed a tiered categorization strategy where AI is only invoked for ambiguous files or when explicitly requested, keeping the default experience near-instant.
- **Dependency Isolation**: Some users don't need ML or AI features.
    - **Lesson**: Used lazy imports and robust `ImportError` handling to ensure the core CLI remains functional even if heavy libraries like Scikit-learn or FAISS aren't installed.

## Why I Built This
I built F.O.R.G.E. because my local filesystem had become a "black hole" where data went to die. Traditional search tools were too slow, and manual organization was a chore I always skipped. I wanted a tool that didn't just move files, but actually *understood* them, giving me a clean workspace and the ability to find a document I haven't seen in months using only my memory of what it was about.

## Future Improvements
- [ ] System tray integration for the Watchdog service.
- [ ] Web-based dashboard for viewing file analytics and editing categories.
- [ ] Support for cloud storage providers (S3/Drive) as targets or destinations.

## Author
**Jay**
[GitHub Profile](https://github.com/jay)
