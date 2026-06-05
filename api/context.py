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


def restore_and_sync_settings(store, runtime) -> None:
    import json
    import logging
    logger = logging.getLogger("mobguard.settings_sync")
    
    try:
        with store._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_settings_backup (
                    key_name VARCHAR(50) PRIMARY KEY,
                    settings_json TEXT NOT NULL
                )
                """
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to initialize runtime_settings_backup table: %s", exc)
        return

    db_settings = {}
    try:
        with store._connect() as conn:
            row = conn.execute(
                "SELECT settings_json FROM runtime_settings_backup WHERE key_name = ?",
                ("global",)
            ).fetchone()
            if row:
                db_settings = json.loads(row["settings_json"])
    except Exception as exc:
        logger.warning("Failed to load settings from runtime_settings_backup: %s", exc)

    config_path = runtime.config_path
    current_config = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                current_config = json.load(f)
        except Exception as exc:
            logger.warning("Failed to read config.json: %s", exc)

    current_settings = current_config.get("settings", {})
    if not isinstance(current_settings, dict):
        current_settings = {}

    needs_save = False
    
    for key, val in db_settings.items():
        curr_val = current_settings.get(key)
        if curr_val in (None, "", [], {}):
            current_settings[key] = val
            needs_save = True

    if current_settings and not db_settings:
        try:
            with store._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO runtime_settings_backup (key_name, settings_json) VALUES (?, ?)",
                    ("global", json.dumps(current_settings, ensure_ascii=False))
                )
                conn.commit()
                logger.info("Backed up current config settings to database.")
        except Exception as exc:
            logger.warning("Failed to backup settings to database: %s", exc)

    if needs_save:
        current_config["settings"] = current_settings
        try:
            config_path.write_text(json.dumps(current_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            logger.info("Restored settings from database backup into config.json")
            runtime.reload_config()
        except Exception as exc:
            logger.warning("Failed to write restored config.json: %s", exc)


def build_container(base_dir: Path | None = None) -> APIContainer:
    root_dir = base_dir or Path(__file__).resolve().parents[1]
    runtime = load_runtime_context(root_dir, os.getenv("BAN_SYSTEM_DIR"))
    storage = build_storage_bundle(runtime)
    store = storage.store
    analysis_store = storage.analysis_store

    is_sqlite = getattr(store.storage, "backend", "sqlite") == "sqlite"
    import sys
    if not is_sqlite and ("pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ):
        return APIContainer(
            runtime=runtime,
            store=store,
            analysis_store=analysis_store,
            session_cookie_name=os.getenv("MOBGUARD_SESSION_COOKIE", "mobguard_session"),
            session_cookie_secure=os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true",
        )

    analysis_store.init_schema()
    store.init_schema()
    restore_and_sync_settings(store, runtime)
    store.sync_runtime_config(runtime.config)
    return APIContainer(
        runtime=runtime,
        store=store,
        analysis_store=analysis_store,
        session_cookie_name=os.getenv("MOBGUARD_SESSION_COOKIE", "mobguard_session"),
        session_cookie_secure=os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true",
    )
