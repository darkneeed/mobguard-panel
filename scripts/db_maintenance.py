from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from mobguard_platform import AnalysisStore, PlatformStore, load_runtime_context


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MobGuard SQLite maintenance")
    parser.add_argument(
        "--mode",
        choices=("periodic", "emergency"),
        default="periodic",
        help="Maintenance mode. emergency also truncates WAL and runs VACUUM.",
    )
    return parser.parse_args()


def _collect_file_sizes(db_path: Path) -> dict[str, Any]:
    wal_path = db_path.with_name(f"{db_path.name}-wal")
    shm_path = db_path.with_name(f"{db_path.name}-shm")
    return {
        "db_path": str(db_path),
        "db_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "wal_path": str(wal_path),
        "wal_size_bytes": wal_path.stat().st_size if wal_path.exists() else 0,
        "shm_path": str(shm_path),
        "shm_size_bytes": shm_path.stat().st_size if shm_path.exists() else 0,
    }


def run(mode: str) -> dict[str, Any]:
    root_dir = Path(__file__).resolve().parents[1]
    runtime = load_runtime_context(root_dir, os.getenv("BAN_SYSTEM_DIR"))
    store = PlatformStore(runtime.db_path, runtime.config, str(runtime.config_path))
    analysis_store = AnalysisStore(runtime.db_path)
    analysis_store.init_schema()
    store.init_schema()
    store.sync_runtime_config(runtime.config)

    before = _collect_file_sizes(Path(runtime.db_path))
    report = store.run_db_maintenance(mode=mode)
    after = _collect_file_sizes(Path(runtime.db_path))
    return {
        "mode": mode,
        "before": before,
        "after": after,
        "report": report,
    }


def main() -> int:
    args = _parse_args()
    payload = run(args.mode)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
