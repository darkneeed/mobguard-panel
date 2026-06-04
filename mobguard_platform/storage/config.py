from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


VALID_DB_BACKENDS = frozenset({"postgres"})


@dataclass(frozen=True)
class DatabaseBackendConfig:
    backend: str
    postgres_dsn: str | None = None
    postgres_host: str | None = None
    postgres_port: int = 5432
    postgres_db: str | None = None
    postgres_user: str | None = None
    postgres_password: str | None = None

    def resolve_postgres_dsn(self) -> str | None:
        if self.postgres_dsn:
            return self.postgres_dsn
        if not self.postgres_host or not self.postgres_db or not self.postgres_user:
            return None
        password = self.postgres_password or ""
        auth = self.postgres_user
        if password:
            auth = f"{auth}:{password}"
        return f"postgresql://{auth}@{self.postgres_host}:{int(self.postgres_port)}/{self.postgres_db}"


def load_database_backend_config(
    settings: dict[str, Any] | None,
    env: Mapping[str, str] | None = None,
) -> DatabaseBackendConfig:
    settings = settings or {}
    env = env or {}
    inferred_dsn = _optional_value(env.get("MOBGUARD_POSTGRES_DSN") or env.get("DATABASE_URL"))
    backend = str(env.get("MOBGUARD_DB_BACKEND") or settings.get("db_backend") or "").strip().lower()
    if not backend:
        backend = "postgres"
    if backend not in VALID_DB_BACKENDS:
        raise ValueError(f"Unsupported database backend: {backend}")
    return DatabaseBackendConfig(
        backend=backend,
        postgres_dsn=_optional_value(inferred_dsn or settings.get("postgres_dsn")),
        postgres_host=_optional_value(env.get("MOBGUARD_POSTGRES_HOST") or settings.get("postgres_host")),
        postgres_port=_coerce_port(env.get("MOBGUARD_POSTGRES_PORT") or settings.get("postgres_port")),
        postgres_db=_optional_value(env.get("MOBGUARD_POSTGRES_DB") or settings.get("postgres_db")),
        postgres_user=_optional_value(env.get("MOBGUARD_POSTGRES_USER") or settings.get("postgres_user")),
        postgres_password=_optional_value(
            env.get("MOBGUARD_POSTGRES_PASSWORD") or settings.get("postgres_password")
        ),
    )


def _optional_value(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _coerce_port(value: Any, default: int = 5432) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
