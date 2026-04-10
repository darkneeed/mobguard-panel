from __future__ import annotations

from dataclasses import dataclass

from ..storage.sqlite import SQLiteStorage


@dataclass
class SQLiteRepository:
    storage: SQLiteStorage

    def connect(self):
        return self.storage.connect()

    def table_exists(self, conn, table_name: str) -> bool:
        return self.storage.table_exists(conn, table_name)
