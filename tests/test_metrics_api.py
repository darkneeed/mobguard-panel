import json
import shutil
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from api.routers import metrics as metrics_router
from api.routers import modules as modules_router
from api.services import modules as module_service
from mobguard_platform import AnalysisStore, PlatformStore


class MetricsAPITests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-metrics-api-")
        self.root = Path(self.temp_dir)
        self.runtime_dir = self.root / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.runtime_dir / "config.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "mobile_tags": ["SELFSTEAL_RU-YANDEX_TCP"],
                    "settings": {
                        "threshold_mobile": 60,
                        "review_ui_base_url": "https://mobguard.example.com",
                    },
                    "_meta": {"revision": 3, "updated_at": "2026-04-11T10:00:00", "updated_by": "system"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.db_path = str(self.runtime_dir / "bans.db")
        self.store = PlatformStore(self.db_path, {"settings": {}}, str(self.config_path))
        self.analysis_store = AnalysisStore(self.db_path)
        self.analysis_store.init_schema()
        self.store.init_schema()
        self.store.sync_runtime_config(json.loads(self.config_path.read_text(encoding="utf-8")))
        self.container = SimpleNamespace(store=self.store, analysis_store=self.analysis_store)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_metrics_overview_returns_stale_snapshot_quickly_when_sqlite_is_locked(self):
        seeded = metrics_router.get_overview(_={}, container=self.container)
        self.assertFalse(seeded["pipeline"]["stale"])

        started_at = time.monotonic()
        with patch.object(self.store, "_read_snapshot_payload", side_effect=sqlite3.OperationalError("database is locked")):
            payload = metrics_router.get_overview(_={}, container=self.container)
        elapsed = time.monotonic() - started_at

        self.assertLess(elapsed, 2.0)
        self.assertEqual(payload["quality"], seeded["quality"])
        self.assertTrue(payload["pipeline"]["stale"])

    def test_metrics_overview_returns_fast_503_when_snapshot_is_missing_and_sqlite_is_locked(self):
        self.store._read_cache.clear()
        started_at = time.monotonic()
        with patch.object(self.store, "_read_snapshot_payload", return_value=None):
            with patch.object(self.store, "refresh_overview_snapshot", side_effect=sqlite3.OperationalError("database is locked")):
                with self.assertRaises(HTTPException) as ctx:
                    metrics_router.get_overview(_={}, container=self.container)
        elapsed = time.monotonic() - started_at

        self.assertLess(elapsed, 2.0)
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("temporarily unavailable", ctx.exception.detail)

    def test_admin_modules_returns_pipeline_freshness_fields_without_blocking(self):
        self.store.create_managed_module(
            "node-a",
            "token-a",
            "encrypted-token-a",
            module_name="Node A",
            metadata={"inbound_tags": ["SELFSTEAL_RU-YANDEX_TCP"]},
        )
        module_service.register_module(
            self.container,
            {
                "module_id": "node-a",
                "module_name": "Node A",
                "version": "1.0.0",
                "protocol_version": "v1",
            },
            "token-a",
        )

        seeded = modules_router.admin_list_modules(_={}, container=self.container)
        self.assertIn("snapshot_updated_at", seeded["pipeline"])
        self.assertIn("snapshot_age_seconds", seeded["pipeline"])
        self.assertIn("stale", seeded["pipeline"])

        started_at = time.monotonic()
        with patch.object(self.store, "_read_snapshot_payload", side_effect=sqlite3.OperationalError("database is locked")):
            payload = modules_router.admin_list_modules(_={}, container=self.container)
        elapsed = time.monotonic() - started_at

        self.assertLess(elapsed, 2.0)
        self.assertIn("snapshot_updated_at", payload["pipeline"])
        self.assertIn("snapshot_age_seconds", payload["pipeline"])
        self.assertTrue(payload["pipeline"]["stale"])

    def test_metrics_overview_includes_realtime_usage_summary(self):
        with self.store._connect() as conn:
            conn.execute(
                "INSERT INTO active_trackers (key, start_time, last_seen) VALUES (?, ?, ?)",
                ("uuid-1:1.1.1.1", "2026-04-12T03:00:00", "9999-04-12T03:20:00"),
            )
            conn.execute(
                "INSERT INTO active_trackers (key, start_time, last_seen) VALUES (?, ?, ?)",
                ("uuid-2:2.2.2.2", "2026-04-12T03:05:00", "9999-04-12T03:20:00"),
            )
            conn.execute(
                """
                INSERT INTO violations (
                    uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("uuid-1", 1, None, None, "2026-04-12T03:18:00", "2026-04-12T03:18:00", 1),
            )
            conn.commit()

        payload = metrics_router.get_overview(_={}, container=self.container)

        self.assertEqual(payload["realtime_usage"]["active_users"], 2)
        self.assertEqual(payload["realtime_usage"]["violating_users"], 1)
        self.assertEqual(payload["realtime_usage"]["compliant_users"], 1)
        self.assertIn("panel_server", payload)
        self.assertIn("memory_total_bytes", payload["panel_server"])

    def test_admin_modules_includes_runtime_summary_and_latest_heartbeat_metrics(self):
        self.store.create_managed_module(
            "node-metrics",
            "token-metrics",
            "encrypted-token-metrics",
            module_name="Node Metrics",
            metadata={"inbound_tags": ["SELFSTEAL_RU-YANDEX_TCP"]},
        )
        module_service.register_module(
            self.container,
            {
                "module_id": "node-metrics",
                "module_name": "Node Metrics",
                "version": "1.0.0",
                "protocol_version": "v1",
            },
            "token-metrics",
        )
        module_service.record_module_heartbeat(
            self.container,
            {
                "module_id": "node-metrics",
                "status": "online",
                "version": "1.0.1",
                "protocol_version": "v1",
                "config_revision_applied": 3,
                "details": {
                    "health_status": "ok",
                    "error_text": "",
                    "last_validation_at": "2026-04-11T10:01:00",
                    "spool_depth": 1,
                    "access_log_exists": True,
                    "system": {
                        "cpu_percent": 23.5,
                        "memory_total_bytes": 4096,
                        "memory_used_bytes": 2048,
                        "memory_percent": 50.0,
                        "disk_total_bytes": 8192,
                        "disk_used_bytes": 4096,
                        "disk_percent": 50.0,
                    },
                    "processes": {
                        "match_count": 1,
                        "cpu_percent": 0.5,
                        "rss_bytes": 1024,
                        "top": [
                            {
                                "pid": 100,
                                "name": "python",
                                "cmdline": "python -m mobguard_module.main",
                                "cpu_percent": 0.5,
                                "rss_bytes": 1024,
                            }
                        ],
                    },
                    "collected_at": "2026-04-11T10:01:00",
                },
            },
            "token-metrics",
        )
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO analysis_events (
                    created_at, module_id, module_name, source_event_uid, decision_source,
                    case_scope_key, device_scope_key, scope_type, subject_key,
                    uuid, username, system_id, telegram_id, ip, tag,
                    verdict, confidence_band, score, isp, asn,
                    asn_source, provider_source, hard_flags_json,
                    punitive_eligible, reasons_json, signal_flags_json, bundle_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "9999-04-11T10:00:00",
                    "node-metrics",
                    "Node Metrics",
                    "evt-1",
                    "rule_engine",
                    "scope-1",
                    "device-1",
                    "subject_ip",
                    "subject-1",
                    "uuid-1",
                    "alice",
                    None,
                    None,
                    "1.2.3.4",
                    "SELFSTEAL_RU-YANDEX_TCP",
                    "MOBILE",
                    "UNSURE",
                    0,
                    "",
                    None,
                    "unknown",
                    "unknown",
                    "[]",
                    0,
                    "[]",
                    "{}",
                    "{}",
                ),
            )
            conn.execute(
                """
                INSERT INTO analysis_events (
                    created_at, module_id, module_name, source_event_uid, decision_source,
                    case_scope_key, device_scope_key, scope_type, subject_key,
                    uuid, username, system_id, telegram_id, ip, tag,
                    verdict, confidence_band, score, isp, asn,
                    asn_source, provider_source, hard_flags_json,
                    punitive_eligible, reasons_json, signal_flags_json, bundle_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "9999-04-11T10:00:01",
                    "node-metrics",
                    "Node Metrics",
                    "evt-2",
                    "rule_engine",
                    "scope-2",
                    "device-2",
                    "subject_ip",
                    "subject-2",
                    "uuid-2",
                    "bob",
                    None,
                    None,
                    "1.2.3.5",
                    "SELFSTEAL_RU-YANDEX_TCP",
                    "MOBILE",
                    "UNSURE",
                    0,
                    "",
                    None,
                    "unknown",
                    "unknown",
                    "[]",
                    0,
                    "[]",
                    "{}",
                    "{}",
                ),
            )
            conn.commit()
        from api.services import modules as modules_service
        modules_service._ACTIVITY_SNAPSHOT_CACHE = None
        modules_service._HEARTBEAT_DETAIL_CACHE.clear()

        payload = modules_router.admin_list_modules(_={}, container=self.container)

        self.assertIn("summary", payload)
        self.assertEqual(payload["summary"]["active_users_total"], 2)
        self.assertEqual(payload["summary"]["recent_events_total"], 2)
        self.assertEqual(payload["summary"]["avg_cpu_percent"], 23.5)
        self.assertEqual(payload["summary"]["memory_total_bytes"], 4096)
        self.assertEqual(payload["summary"]["mobguard_process_rss_bytes"], 1024)
        self.assertEqual(payload["items"][0]["runtime_metrics"]["active_users"], 2)
        self.assertEqual(payload["items"][0]["runtime_metrics"]["recent_events"], 2)
        self.assertEqual(payload["items"][0]["runtime_metrics"]["system"]["cpu_percent"], 23.5)
        self.assertEqual(payload["items"][0]["runtime_metrics"]["processes"]["match_count"], 1)
