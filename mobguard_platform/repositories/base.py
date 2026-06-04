from __future__ import annotations

from dataclasses import dataclass
from typing import Any

@dataclass
class SQLiteRepository:
    storage: Any

    def connect(self):
        return self.storage.connect()

    def table_exists(self, conn, table_name: str) -> bool:
        if hasattr(self.storage, "table_exists"):
            return self.storage.table_exists(conn, table_name)
        # Fallback for simple mocks
        row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,)).fetchone()
        return row is not None
