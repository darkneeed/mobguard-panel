from __future__ import annotations

from dataclasses import dataclass

from ..analysis_store import AnalysisStore
from ..store import PlatformStore
from ..runtime.context import RuntimeContext


@dataclass(frozen=True)
class StorageBundle:
    backend: str
    store: PlatformStore
    analysis_store: AnalysisStore


def build_storage_bundle(runtime: RuntimeContext) -> StorageBundle:
    if runtime.database.backend == "sqlite":
        db_path = runtime.database.sqlite_path or runtime.db_path
        return StorageBundle(
            backend="sqlite",
            store=PlatformStore(db_path, runtime.config, str(runtime.config_path)),
            analysis_store=AnalysisStore(db_path),
        )
    raise NotImplementedError(
        "Postgres runtime backend is not wired yet; use scripts/migrate_sqlite_to_postgres.py to prepare staged cutover."
    )
