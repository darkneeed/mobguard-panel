from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from mobguard_platform import PlatformStore, RuntimeContext, load_runtime_context


@dataclass
class APIContainer:
    runtime: RuntimeContext
    store: PlatformStore
    session_cookie_name: str
    session_cookie_secure: bool


def build_container(base_dir: Path | None = None) -> APIContainer:
    root_dir = base_dir or Path(__file__).resolve().parents[1]
    runtime = load_runtime_context(root_dir, os.getenv("BAN_SYSTEM_DIR"))
    store = PlatformStore(runtime.db_path, runtime.config, str(runtime.config_path))
    store.init_schema()
    store.sync_runtime_config(runtime.config)
    return APIContainer(
        runtime=runtime,
        store=store,
        session_cookie_name=os.getenv("MOBGUARD_SESSION_COOKIE", "mobguard_session"),
        session_cookie_secure=os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true",
    )
