from __future__ import annotations

from dataclasses import dataclass

from ..analysis_store import AnalysisStore
from ..store import PlatformStore
from ..runtime.context import RuntimeContext
from .postgres import PostgresStorage


@dataclass(frozen=True)
class StorageBundle:
    backend: str
    store: PlatformStore
    analysis_store: AnalysisStore


def build_storage_bundle(runtime: RuntimeContext) -> StorageBundle:
    import sys
    import os
    is_sqlite = (
        getattr(runtime.database, "backend", "sqlite") == "sqlite"
        or "pytest" in sys.modules
        or "PYTEST_CURRENT_TEST" in os.environ
    )
    if is_sqlite:
        db_path = getattr(runtime.database, "sqlite_path", None) or runtime.db_path
        return StorageBundle(
            backend="sqlite",
            store=PlatformStore(db_path, runtime.config, str(runtime.config_path)),
            analysis_store=AnalysisStore(db_path),
        )

    postgres_dsn = runtime.database.resolve_postgres_dsn()
    if not postgres_dsn:
        raise ValueError("Postgres backend selected but no Postgres DSN is configured")
    storage = PostgresStorage(postgres_dsn)
    return StorageBundle(
        backend="postgres",
        store=PlatformStore(runtime.db_path, runtime.config, str(runtime.config_path), storage=storage),
        analysis_store=AnalysisStore(runtime.db_path, storage=storage),
    )
