from __future__ import annotations

import copy
import ntpath
import os
import posixpath
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_DIR = "/opt/mobguard/runtime"
LEGACY_RUNTIME_DIR = "/opt/ban_system"
DB_FILENAME = "bans.db"
GEOIP_DB_FILENAME = "GeoLite2-ASN.mmdb"
RUNTIME_DIRNAME = "runtime"


def resolve_runtime_dir(base_dir: str | Path, explicit: str | None = None) -> str:
    if explicit:
        return explicit

    base_dir = os.fspath(base_dir)
    candidates = [
        os.path.join(base_dir, "runtime"),
        DEFAULT_RUNTIME_DIR,
        LEGACY_RUNTIME_DIR,
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return DEFAULT_RUNTIME_DIR


def runtime_db_path(runtime_dir: str | Path) -> str:
    return _join_runtime_path(runtime_dir, DB_FILENAME)


def runtime_geoip_db_path(runtime_dir: str | Path) -> str:
    return _join_runtime_path(runtime_dir, GEOIP_DB_FILENAME)


def storage_runtime_db_path(runtime_dir: str | Path) -> str:
    return _storage_runtime_path(runtime_dir, DB_FILENAME)


def storage_runtime_geoip_db_path(runtime_dir: str | Path) -> str:
    return _storage_runtime_path(runtime_dir, GEOIP_DB_FILENAME)


def normalize_runtime_bound_settings(
    config: dict[str, Any],
    runtime_dir: str | Path,
) -> dict[str, Any]:
    normalized = copy.deepcopy(config)
    settings = normalized.setdefault("settings", {})
    settings["db_file"] = runtime_db_path(runtime_dir)
    settings["geoip_db"] = runtime_geoip_db_path(runtime_dir)
    return normalized


def canonicalize_runtime_bound_settings(
    config: dict[str, Any],
    runtime_dir: str | Path,
) -> dict[str, Any]:
    canonicalized = copy.deepcopy(config)
    settings = canonicalized.setdefault("settings", {})
    settings["db_file"] = storage_runtime_db_path(runtime_dir)
    settings["geoip_db"] = storage_runtime_geoip_db_path(runtime_dir)
    return canonicalized


def _join_runtime_path(runtime_dir: str | Path, filename: str) -> str:
    runtime_dir = os.fspath(runtime_dir)
    if "\\" in runtime_dir or (len(runtime_dir) >= 2 and runtime_dir[1] == ":"):
        return ntpath.join(runtime_dir, filename)
    return posixpath.join(runtime_dir, filename)


def _storage_runtime_path(runtime_dir: str | Path, filename: str) -> str:
    runtime_dir = os.fspath(runtime_dir)
    if os.path.basename(os.path.normpath(runtime_dir)) == RUNTIME_DIRNAME:
        return posixpath.join(RUNTIME_DIRNAME, filename)
    return filename
