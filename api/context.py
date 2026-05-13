from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from mobguard_platform import AnalysisStore, PlatformStore, RuntimeContext, load_runtime_context
from mobguard_platform.storage.factory import build_storage_bundle


@dataclass
class APIContainer:
    runtime: RuntimeContext
    store: PlatformStore
    analysis_store: AnalysisStore
    session_cookie_name: str
    session_cookie_secure: bool


def build_container(base_dir: Path | None = None) -> APIContainer:
    root_dir = base_dir or Path(__file__).resolve().parents[1]
    runtime = load_runtime_context(root_dir, os.getenv("BAN_SYSTEM_DIR"))
    storage = build_storage_bundle(runtime)
    store = storage.store
    analysis_store = storage.analysis_store
    analysis_store.init_schema()
    store.init_schema()
    store.sync_runtime_config(runtime.config)
    return APIContainer(
        runtime=runtime,
        store=store,
        analysis_store=analysis_store,
        session_cookie_name=os.getenv("MOBGUARD_SESSION_COOKIE", "mobguard_session"),
        session_cookie_secure=os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true",
    )
