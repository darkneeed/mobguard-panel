from __future__ import annotations

import os
import platform
import shutil
import socket
import time
from pathlib import Path
from typing import Any

_PREV_CPU_TIMES: tuple[int, int] | None = None
_LAST_CPU_PERCENT: float | None = None


def _safe_read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _read_cpu_percent() -> float | None:
    global _PREV_CPU_TIMES, _LAST_CPU_PERCENT
    raw = _safe_read_text("/proc/stat")
    first_line = raw.splitlines()[0] if raw else ""
    parts = first_line.split()
    if len(parts) < 5:
        return _LAST_CPU_PERCENT
    try:
        values = [int(value) for value in parts[1:]]
    except ValueError:
        return _LAST_CPU_PERCENT
    idle = values[3]
    total = sum(values)
    if _PREV_CPU_TIMES is None:
        _PREV_CPU_TIMES = (idle, total)
        return _LAST_CPU_PERCENT
    prev_idle, prev_total = _PREV_CPU_TIMES
    _PREV_CPU_TIMES = (idle, total)
    delta_total = max(total - prev_total, 0)
    delta_idle = max(idle - prev_idle, 0)
    if delta_total <= 0:
        return _LAST_CPU_PERCENT
    usage = (1.0 - delta_idle / delta_total) * 100.0
    _LAST_CPU_PERCENT = round(max(0.0, min(100.0, usage)), 1)
    return _LAST_CPU_PERCENT


def _read_memory() -> tuple[int, int, float | None]:
    raw = _safe_read_text("/proc/meminfo")
    if not raw:
        return (0, 0, None)
    values: dict[str, int] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, tail = line.split(":", 1)
        parts = tail.strip().split()
        if not parts:
            continue
        try:
            values[key.strip()] = int(parts[0]) * 1024
        except ValueError:
            continue
    total = int(values.get("MemTotal", 0))
    available = int(values.get("MemAvailable", 0))
    used = total - available if total and available else total
    percent = round((used / total) * 100.0, 1) if total > 0 else None
    return (total, max(used, 0), percent)


def _read_disk() -> tuple[int, int, float | None]:
    try:
        usage = shutil.disk_usage("/")
    except OSError:
        return (0, 0, None)
    total = int(usage.total)
    used = int(usage.used)
    percent = round((used / total) * 100.0, 1) if total > 0 else None
    return (total, used, percent)


def _read_uptime_seconds() -> int | None:
    raw = _safe_read_text("/proc/uptime").strip()
    if not raw:
        return None
    try:
        return max(int(float(raw.split()[0])), 0)
    except (IndexError, ValueError):
        return None


def _read_process_memory() -> int | None:
    raw = _safe_read_text("/proc/self/statm").strip()
    if not raw:
        return None
    parts = raw.split()
    if len(parts) < 2:
        return None
    try:
        rss_pages = int(parts[1])
    except ValueError:
        return None
    page_size = int(os.sysconf("SC_PAGE_SIZE"))
    return max(rss_pages, 0) * page_size


def collect_panel_server_snapshot() -> dict[str, Any]:
    memory_total, memory_used, memory_percent = _read_memory()
    disk_total, disk_used, disk_percent = _read_disk()
    cpu_percent = _read_cpu_percent()
    load_1m = load_5m = load_15m = None
    try:
        load_1m, load_5m, load_15m = os.getloadavg()
    except (AttributeError, OSError):
        pass
    return {
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "cpu_percent": cpu_percent,
        "cpu_cores": int(os.cpu_count() or 0),
        "load_avg_1m": round(float(load_1m), 2) if load_1m is not None else None,
        "load_avg_5m": round(float(load_5m), 2) if load_5m is not None else None,
        "load_avg_15m": round(float(load_15m), 2) if load_15m is not None else None,
        "memory_total_bytes": memory_total,
        "memory_used_bytes": memory_used,
        "memory_percent": memory_percent,
        "disk_total_bytes": disk_total,
        "disk_used_bytes": disk_used,
        "disk_percent": disk_percent,
        "uptime_seconds": _read_uptime_seconds(),
        "api_process_rss_bytes": _read_process_memory(),
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
    }
