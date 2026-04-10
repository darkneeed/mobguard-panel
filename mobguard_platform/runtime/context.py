from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .paths import normalize_runtime_bound_settings, resolve_runtime_dir


@dataclass
class RuntimeContext:
    root_dir: Path
    runtime_dir: Path
    env_path: Path
    config_path: Path
    config: dict[str, Any]
    env: dict[str, str]

    @property
    def settings(self) -> dict[str, Any]:
        return self.config.setdefault("settings", {})

    @property
    def db_path(self) -> str:
        return str(self.settings["db_file"])

    def reload_config(self) -> dict[str, Any]:
        with self.config_path.open("r", encoding="utf-8") as handle:
            self.config = normalize_runtime_bound_settings(json.load(handle), self.runtime_dir)
        return self.config

    def reload_env(self) -> dict[str, str]:
        load_dotenv(self.env_path, override=True)
        self.env = {key: str(value) for key, value in os.environ.items()}
        return self.env


def ensure_runtime_layout(runtime_dir: str | Path) -> Path:
    runtime_path = Path(runtime_dir)
    runtime_path.mkdir(parents=True, exist_ok=True)
    (runtime_path / "health").mkdir(parents=True, exist_ok=True)
    db_path = runtime_path / "bans.db"
    if not db_path.exists():
        db_path.touch()
    return runtime_path


def load_runtime_context(base_dir: str | Path, explicit_runtime_dir: str | None = None) -> RuntimeContext:
    root_dir = Path(base_dir).resolve()
    runtime_dir = ensure_runtime_layout(resolve_runtime_dir(root_dir, explicit_runtime_dir))
    env_path = Path(os.getenv("MOBGUARD_ENV_FILE", str(runtime_dir.parent / ".env")))
    load_dotenv(env_path)
    config_path = runtime_dir / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Required runtime config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        config = normalize_runtime_bound_settings(json.load(handle), runtime_dir)
    env = {key: str(value) for key, value in os.environ.items()}
    return RuntimeContext(
        root_dir=root_dir,
        runtime_dir=runtime_dir,
        env_path=env_path,
        config_path=config_path,
        config=config,
        env=env,
    )
