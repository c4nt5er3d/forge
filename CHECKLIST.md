# FORGE Functional Checklist

Run through this checklist after refactors or dependency changes.

## 1. Core Organization
- [ ] **Organize**: `forge organize <folder> <destination>` moves files into category folders.
- [ ] **Copy Mode**: `forge copy <source> <destination>` copies files and leaves originals in place.
- [ ] **Preview**: `forge organize <folder> --preview` shows planned changes without moving files.
- [ ] **Undo**: `forge undo --preview` previews the latest transaction, and `forge undo --steps 1` reverts it.
- [ ] **Organize Flags**: Verify `--recursive`, `--exclude`, `--date-sort`, `--smart`, `--local`, and `--env`.

## 2. Advanced Features
- [ ] **ML Classifier**: `forge train <organized_folder>` creates/updates `models/classifier.joblib`.
- [ ] **Search**: `forge index <folder>` then `forge search "<query>"` returns scored matches.
- [ ] **Smart Renaming**: `forge rename <folder> --preview` shows readable proposed names, and unsupported/noisy files are skipped unchanged.
- [ ] **Local LLM Rename**: `forge rename <folder> --local` uses Ollama when installed and still avoids unsafe filenames.

## 3. Real-Time Monitoring
- [ ] **Watchdog**: `forge watch <folder> <destination>` moves new files using configured categories.
- [ ] **Recursive Watch**: `forge watch <folder> <destination> --recursive` observes nested folders.
- [ ] **Git Ignore**: Files inside `.git/` do not trigger watcher processing.

## 4. System Integrity
- [ ] **Config Validation**: Corrupt `config.json` or `categories.json` and verify startup reports the error.
- [ ] **Logging**: Check repo-local `logs/organizer_*.log` after running a command.
- [ ] **Dependencies**: Verify `pip install .` starts the core CLI without ML/AI extras.

## 5. Deployment/Tests
- [ ] **Tests**: Run `python -m pytest tests/`.
- [ ] **CI Status**: Ensure GitHub Actions are green on supported OSes.
