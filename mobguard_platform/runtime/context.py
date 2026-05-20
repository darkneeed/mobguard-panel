from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from ..storage.config import DatabaseBackendConfig, load_database_backend_config

from .paths import normalize_runtime_bound_settings, resolve_runtime_dir

logger = logging.getLogger(__name__)


@dataclass
class RuntimeContext:
    root_dir: Path
    runtime_dir: Path
    env_path: Path
    config_path: Path
    config: dict[str, Any]
    env: dict[str, str]
    database: DatabaseBackendConfig

    @property
    def settings(self) -> dict[str, Any]:
        return self.config.setdefault("settings", {})

    @property
    def db_path(self) -> str:
        return str(self.settings["db_file"])

    def reload_config(self) -> dict[str, Any]:
        self.config = _load_runtime_config_payload(self.config_path, self.runtime_dir)
        self.database = load_database_backend_config(self.config.get("settings", {}), self.env)
        return self.config

    def reload_env(self) -> dict[str, str]:
        load_dotenv(self.env_path, override=True)
        self.env = {key: str(value) for key, value in os.environ.items()}
        self.database = load_database_backend_config(self.config.get("settings", {}), self.env)
        return self.env


def ensure_runtime_layout(runtime_dir: str | Path) -> Path:
    runtime_path = Path(runtime_dir)
    runtime_path.mkdir(parents=True, exist_ok=True)
    (runtime_path / "health").mkdir(parents=True, exist_ok=True)
    db_path = runtime_path / "bans.db"
    if not db_path.exists():
        db_path.touch()
    return runtime_path


def _safe_runtime_config_default() -> dict[str, Any]:
    return {"settings": {}}


def _load_runtime_config_payload(config_path: Path, runtime_dir: Path) -> dict[str, Any]:
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to read runtime config: {config_path}") from exc

    stripped = raw.strip()
    if not stripped:
        fallback = normalize_runtime_bound_settings(_safe_runtime_config_default(), runtime_dir)
        config_path.write_text(json.dumps(fallback, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        logger.warning("Runtime config was empty; restored default config at %s", config_path)
        return fallback

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        fallback = normalize_runtime_bound_settings(_safe_runtime_config_default(), runtime_dir)
        config_path.write_text(json.dumps(fallback, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        logger.warning(
            "Runtime config was invalid JSON and got reset to defaults at %s: %s",
            config_path,
            exc,
        )
        return fallback

    if not isinstance(parsed, dict):
        fallback = normalize_runtime_bound_settings(_safe_runtime_config_default(), runtime_dir)
        config_path.write_text(json.dumps(fallback, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        logger.warning("Runtime config had non-object root; restored default config at %s", config_path)
        return fallback

    return normalize_runtime_bound_settings(parsed, runtime_dir)


def load_runtime_context(base_dir: str | Path, explicit_runtime_dir: str | None = None) -> RuntimeContext:
    root_dir = Path(base_dir).resolve()
    runtime_dir = ensure_runtime_layout(resolve_runtime_dir(root_dir, explicit_runtime_dir))
    env_path = Path(os.getenv("MOBGUARD_ENV_FILE", str(runtime_dir.parent / ".env")))
    load_dotenv(env_path)
    config_path = runtime_dir / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Required runtime config not found: {config_path}")
    config = _load_runtime_config_payload(config_path, runtime_dir)
    env = {key: str(value) for key, value in os.environ.items()}
    database = load_database_backend_config(config.get("settings", {}), env)
    return RuntimeContext(
        root_dir=root_dir,
        runtime_dir=runtime_dir,
        env_path=env_path,
        config_path=config_path,
        config=config,
        env=env,
        database=database,
    )
