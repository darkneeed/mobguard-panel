from __future__ import annotations

import os
import re
from typing import Any


ENV_LINE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def read_env_file(path: str) -> dict[str, str]:
    values: dict[str, str] = {
        key: str(value)
        for key, value in os.environ.items()
    }
    if not os.path.exists(path):
        return values
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            match = ENV_LINE_RE.match(line)
            if not match:
                continue
            key, value = match.groups()
            values[key] = value
    return values


def update_env_file(path: str, updates: dict[str, Any]) -> None:
    status = get_env_file_status(path)
    if not status["exists"]:
        raise ValueError(f"Env file is unavailable for writing: {path}")
    if not status["writable"]:
        raise ValueError(f"Env file is read-only: {path}")

    lines: list[str] = []
    existing_indexes: dict[str, int] = {}

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        for index, line in enumerate(lines):
            match = ENV_LINE_RE.match(line)
            if match:
                existing_indexes[match.group(1)] = index

    for key, raw_value in updates.items():
        value = "" if raw_value is None else str(raw_value)
        line = f"{key}={value}"
        if key in existing_indexes:
            lines[existing_indexes[key]] = line
        else:
            lines.append(line)

    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + ("\n" if lines else ""))


def get_env_file_status(path: str) -> dict[str, Any]:
    exists = os.path.isfile(path)
    writable = exists and os.access(path, os.W_OK)
    return {
        "path": path,
        "exists": exists,
        "writable": writable,
    }


def env_field_payload(key: str, values: dict[str, str], *, masked: bool, restart_required: bool) -> dict[str, Any]:
    raw_value = values.get(key, "")
    present = raw_value != ""
    payload: dict[str, Any] = {
        "key": key,
        "present": present,
        "masked": masked,
        "restart_required": restart_required,
    }
    if masked:
        payload["value"] = _mask_secret(raw_value) if present else ""
    else:
        payload["value"] = raw_value
    return payload


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}{'*' * max(len(value) - 4, 1)}{value[-2:]}"
