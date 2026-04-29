from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import sqlite3
import threading


class OrganizerDatabase:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_path TEXT NOT NULL,
                    current_path TEXT,
                    destination_path TEXT,
                    file_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    confidence REAL DEFAULT 0,
                    method TEXT DEFAULT '',
                    mime_type TEXT DEFAULT '',
                    extractor TEXT DEFAULT '',
                    status TEXT NOT NULL,
                    error TEXT DEFAULT '',
                    extracted_preview TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    moved_at TEXT,
                    undone_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_actions_created_at
                ON actions(created_at DESC)
                """
            )

    def record_action(self, payload: Dict[str, Any]) -> int:
        fields = [
            "original_path",
            "current_path",
            "destination_path",
            "file_name",
            "category",
            "confidence",
            "method",
            "mime_type",
            "extractor",
            "status",
            "error",
            "extracted_preview",
            "moved_at",
        ]
        values = [payload.get(field) for field in fields]
        placeholders = ", ".join("?" for _ in fields)
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                f"INSERT INTO actions ({', '.join(fields)}) VALUES ({placeholders})",
                values,
            )
            return int(cursor.lastrowid)

    def list_actions(self, limit: int = 100) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM actions ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_action(self, action_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
        return dict(row) if row else None

    def mark_undone(self, action_id: int, current_path: str, status: str = "undone") -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE actions
                SET current_path = ?, status = ?, undone_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (current_path, status, action_id),
            )

    def mark_reclassified(
        self,
        action_id: int,
        category: str,
        current_path: str,
        destination_path: str,
        confidence: float = 1.0,
        method: str = "manual",
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE actions
                SET category = ?,
                    current_path = ?,
                    destination_path = ?,
                    confidence = ?,
                    method = ?,
                    status = 'reclassified',
                    moved_at = CURRENT_TIMESTAMP,
                    error = ''
                WHERE id = ?
                """,
                (category, current_path, destination_path, confidence, method, action_id),
            )

    def record_error(self, original_path: str, file_name: str, error: str) -> int:
        return self.record_action(
            {
                "original_path": original_path,
                "current_path": original_path,
                "destination_path": "",
                "file_name": file_name,
                "category": "Uncategorized",
                "confidence": 0,
                "method": "error",
                "mime_type": "",
                "extractor": "",
                "status": "error",
                "error": error,
                "extracted_preview": "",
                "moved_at": None,
            }
        )

