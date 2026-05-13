import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


class StateManager:
    """SQLite-backed state for incremental ingest."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path is not None else Path.home() / ".forge" / "state.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    path TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL,
                    mtime REAL NOT NULL,
                    last_processed TEXT,
                    status TEXT DEFAULT 'pending'
                )
                """
            )

    def file_sha256(self, file_path: Path) -> str:
        digest = hashlib.sha256()
        with open(file_path, "rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def is_unchanged(self, file_path: Path) -> bool:
        path = str(file_path.resolve())
        if not file_path.exists():
            return False
        sha256 = self.file_sha256(file_path)
        mtime = file_path.stat().st_mtime
        with self._connect() as conn:
            row = conn.execute(
                "SELECT sha256, mtime, status FROM files WHERE path = ?",
                (path,),
            ).fetchone()
        return bool(row and row[0] == sha256 and row[1] == mtime and row[2] == "processed")

    def mark_processed(self, file_path: Path, status: str = "processed") -> None:
        self._mark(file_path, status=status)

    def mark_errored(self, file_path: Path) -> None:
        self._mark(file_path, status="errored")

    def _mark(self, file_path: Path, status: str) -> None:
        path = str(file_path.resolve())
        sha256 = self.file_sha256(file_path)
        mtime = file_path.stat().st_mtime
        processed_at = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO files (path, sha256, mtime, last_processed, status)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    sha256 = excluded.sha256,
                    mtime = excluded.mtime,
                    last_processed = excluded.last_processed,
                    status = excluded.status
                """,
                (path, sha256, mtime, processed_at, status),
            )

    def get_status(self, file_path: Path) -> Optional[str]:
        path = str(file_path.resolve())
        with self._connect() as conn:
            row = conn.execute("SELECT status FROM files WHERE path = ?", (path,)).fetchone()
        return row[0] if row else None
