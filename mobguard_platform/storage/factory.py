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
    postgres_dsn = runtime.database.resolve_postgres_dsn()
    if not postgres_dsn:
        raise ValueError("Postgres backend selected but no Postgres DSN is configured")
    storage = PostgresStorage(postgres_dsn)
    return StorageBundle(
        backend="postgres",
        store=PlatformStore(runtime.db_path, runtime.config, str(runtime.config_path), storage=storage),
        analysis_store=AnalysisStore(runtime.db_path, storage=storage),
    )
