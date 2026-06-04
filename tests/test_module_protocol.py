import asyncio
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from api.routers import modules as modules_router
from api.schemas.modules import EventBatchRequest
from api.services import ingest_pipeline
from api.services import modules as module_service
from mobguard_platform import AnalysisStore, DecisionBundle, PlatformStore


class ModuleProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-module-protocol-")
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
                        "remnawave_api_url": "https://remna.example.com",
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

    def _assert_no_persisted_enforcement_state(self):
        with self.store._connect() as conn:
            violation_count = conn.execute("SELECT COUNT(*) AS cnt FROM violations").fetchone()["cnt"]
            violation_history_count = conn.execute("SELECT COUNT(*) AS cnt FROM violation_history").fetchone()["cnt"]
            enforcement_job_count = conn.execute("SELECT COUNT(*) AS cnt FROM enforcement_jobs").fetchone()["cnt"]
        self.assertEqual(violation_count, 0)
        self.assertEqual(violation_history_count, 0)
        self.assertEqual(enforcement_job_count, 0)

    def test_register_heartbeat_and_config_roundtrip(self):
        self.store.create_managed_module(
            "node-a",
            "token-a",
            "encrypted-token-a",
            module_name="Node A",
            metadata={
                "inbound_tags": ["SELFSTEAL_RU-YANDEX_TCP"],
            },
        )
        module = module_service.register_module(
            self.container,
            {
                "module_id": "node-a",
                "module_name": "Node A",
                "version": "1.0.0",
                "protocol_version": "v1",
            },
            "token-a",
        )
        self.assertEqual(module["module"]["module_id"], "node-a")
        self.assertEqual(module["config"]["config_revision"], 3)
        self.assertEqual(module["config"]["rules"]["inbound_tags"], ["SELFSTEAL_RU-YANDEX_TCP"])
        self.assertEqual(module["config"]["rules"]["mobile_tags"], ["SELFSTEAL_RU-YANDEX_TCP"])

        heartbeat = module_service.record_module_heartbeat(
            self.container,
            {
                "module_id": "node-a",
                "status": "online",
                "version": "1.0.1",
                "protocol_version": "v1",
                "config_revision_applied": 3,
                "details": {
                    "health_status": "warn",
                    "error_text": "Access log path not found",
                    "last_validation_at": "2026-04-11T10:01:00",
                    "spool_depth": 2,
                    "access_log_exists": False,
                },
            },
            "token-a",
        )
        self.assertEqual(heartbeat["desired_config_revision"], 3)

        payload = module_service.list_modules(self.container)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["module_name"], "Node A")
        self.assertEqual(payload["items"][0]["health_status"], "warn")
        self.assertEqual(payload["items"][0]["error_text"], "Access log path not found")
        self.assertEqual(payload["items"][0]["spool_depth"], 2)
        self.assertFalse(payload["items"][0]["access_log_exists"])

    def test_heartbeat_does_not_backfill_module_name_history(self):
        self.store.create_managed_module(
            "node-heartbeat",
            "token-heartbeat",
            "encrypted-token-heartbeat",
            module_name="Node Heartbeat",
            metadata={"inbound_tags": ["SELFSTEAL_RU-YANDEX_TCP"]},
        )
        self.store.register_module(
            "node-heartbeat",
            "token-heartbeat",
            module_name="Node Heartbeat",
            version="1.0.0",
            protocol_version="v1",
            auto_create=False,
        )
        repo = self.store.modules_admin

        with patch.object(repo, "_backfill_module_name", wraps=repo._backfill_module_name) as mocked_backfill:
            repo.record_module_heartbeat(
                "node-heartbeat",
                status="online",
                version="1.0.1",
                protocol_version="v1",
                config_revision_applied=3,
                details={"health_status": "ok"},
            )

        self.assertEqual(mocked_backfill.call_count, 0)

    def test_resolve_remote_user_prefers_typed_telegram_lookup_when_available(self):
        calls: list[tuple[str, str]] = []

        class TypedClient:
            enabled = True

            def get_user_data_by_telegram_id(self, value):
                calls.append(("tg", str(value)))
                return {"uuid": "uuid-from-tg", "telegramId": str(value)}

            def get_user_data(self, value):
                calls.append(("generic", str(value)))
                return {"uuid": "uuid-from-generic", "telegramId": str(value)}

        runtime = SimpleNamespace(remnawave_client=TypedClient())
        payload = {"telegram_id": "42"}

        result = asyncio.run(module_service._resolve_remote_user(runtime, payload))

        self.assertEqual(result["uuid"], "uuid-from-tg")
        self.assertEqual(result["telegramId"], "42")
        self.assertEqual(calls, [("tg", "42")])

    def test_resolve_remote_user_fallbacks_to_username_when_uuid_payload_lacks_telegram(self):
        calls: list[tuple[str, str]] = []

        class TypedClient:
            enabled = True

            def get_user_data_by_uuid(self, value):
                calls.append(("uuid", str(value)))
                return {"uuid": str(value), "username": "alice"}

            def get_user_data_by_username(self, value):
                calls.append(("username", str(value)))
                return {"uuid": "uuid-from-username", "username": str(value), "telegramId": "1001"}

            def get_user_data(self, value):
                calls.append(("generic", str(value)))
                return {"uuid": "uuid-generic", "username": str(value)}

        runtime = SimpleNamespace(remnawave_client=TypedClient())
        payload = {"uuid": "uuid-1", "username": "alice"}

        result = asyncio.run(module_service._resolve_remote_user(runtime, payload))

        self.assertEqual(result["uuid"], "uuid-1")
        self.assertEqual(result["username"], "alice")
        self.assertEqual(result["telegramId"], "1001")
        self.assertEqual(calls, [("uuid", "uuid-1"), ("username", "alice")])

    def test_resolve_remote_user_uses_raw_username_endpoint_when_cached_profile_has_no_telegram(self):
        calls: list[tuple[str, str]] = []

        class TypedClient:
            enabled = True

            def get_user_data_by_uuid(self, value):
                calls.append(("uuid", str(value)))
                return {"uuid": str(value), "username": "alice"}

            def get_user_data_by_username(self, value):
                calls.append(("username", str(value)))
                return {"uuid": "uuid-1", "username": str(value)}

            def _request(self, method, endpoint, body=None):
                calls.append((method.lower(), str(endpoint)))
                if method == "GET" and endpoint == "/api/users/by-username/alice":
                    return {"response": {"uuid": "uuid-1", "username": "alice", "telegramId": "1001"}}
                return None

            def _extract_user(self, payload):
                if not isinstance(payload, dict):
                    return None
                response = payload.get("response", payload)
                return response if isinstance(response, dict) else None

            def get_user_data(self, value):
                calls.append(("generic", str(value)))
                return {"uuid": "uuid-generic"}

        runtime = SimpleNamespace(remnawave_client=TypedClient())
        payload = {"uuid": "uuid-1", "username": "alice"}

        result = asyncio.run(module_service._resolve_remote_user(runtime, payload))

        self.assertEqual(result["telegramId"], "1001")
        self.assertEqual(
            calls,
            [("uuid", "uuid-1"), ("username", "alice"), ("get", "/api/users/by-username/alice")],
        )

    def test_event_batch_deduplicates_by_event_uid(self):
        self.store.create_managed_module(
            "node-a",
            "token-a",
            "encrypted-token-a",
            module_name="Node A",
            metadata={
                "inbound_tags": ["SELFSTEAL_RU-YANDEX_TCP"],
            },
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

        result = asyncio.run(
            module_service.ingest_module_events(
                self.container,
                {
                    "module_id": "node-a",
                    "protocol_version": "v1",
                    "items": [
                        {
                            "event_uid": "dup-1",
                            "occurred_at": "2026-04-11T12:00:00",
                            "ip": "1.2.3.4",
                            "tag": "SELFSTEAL_RU-YANDEX_TCP",
                            "uuid": "uuid-1",
                        },
                        {
                            "event_uid": "dup-1",
                            "occurred_at": "2026-04-11T12:00:01",
                            "ip": "1.2.3.4",
                            "tag": "SELFSTEAL_RU-YANDEX_TCP",
                            "uuid": "uuid-1",
                        },
                    ],
                },
                "token-a",
            )
        )

        self.assertEqual(result["accepted"], 1)
        self.assertEqual(result["duplicates"], 1)
        self.assertEqual(result["queued"], 1)
        self.assertEqual(result["status"], "queued")

    def test_attach_runtime_metrics_uses_highest_online_signal_for_healthy_module(self):
        modules = [
            {
                "module_id": "module-vk",
                "module_name": "VK",
                "healthy": True,
                "health_status": "ok",
                "install_state": "online",
            }
        ]
        container = SimpleNamespace()

        with (
            patch.object(
                module_service,
                "_heartbeat_detail_map",
                return_value={
                    "module-vk": {
                        "activity": {
                            "active_users": 18,
                            "recent_events": 9,
                            "window_seconds": 60,
                        }
                    }
                },
            ),
            patch.object(
                module_service,
                "_panel_nodes_online_map",
                return_value={"vk": 5},
            ),
            patch.object(
                module_service,
                "_module_remnawave_node_aliases",
                return_value={},
            ),
            patch.object(
                module_service,
                "_activity_snapshot",
                return_value={
                    "window_seconds": 3600,
                    "modules": {
                        "module-vk": {
                            "active_users": 40,
                            "recent_events": 50,
                        }
                    },
                    "totals": {
                        "active_users_total": 40,
                        "recent_events_total": 50,
                    },
                },
            ),
        ):
            items, summary = module_service._attach_runtime_metrics(container, modules)

        self.assertEqual(items[0]["runtime_metrics"]["active_users"], 40)
        self.assertEqual(summary["active_users_total"], 40)

    def test_plan_enforcement_tx_dry_run_warning_does_not_persist_warning_state(self):
        bundle = DecisionBundle(
            ip="1.2.3.4",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=-20,
            isp="ISP",
            punitive_eligible=True,
        )
        runtime = SimpleNamespace(
            settings={
                "dry_run": True,
                "shadow_mode": False,
                "warning_only_mode": False,
                "usage_time_threshold": 0,
                "ban_durations_minutes": [15, 60],
            }
        )

        with self.store._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            enforcement = ingest_pipeline._plan_enforcement_tx(
                conn,
                runtime,
                {"uuid": "uuid-dry-warning"},
                {"ip": "1.2.3.4", "tag": "SELFSTEAL_RU-YANDEX_TCP"},
                bundle,
                event_uid="dry-warning-1",
                analysis_event_id=1,
                review_case_id=None,
            )
            conn.commit()

        self.assertEqual(
            enforcement,
            {
                "type": "warning",
                "warning_count": 1,
                "warning_only": True,
                "delivery_status": "applied",
                "dry_run": True,
            },
        )
        self._assert_no_persisted_enforcement_state()

    def test_plan_enforcement_tx_dry_run_returns_non_persistent_warning(self):
        bundle = DecisionBundle(
            ip="1.2.3.5",
            verdict="HOME",
            confidence_band="HIGH_HOME",
            score=-120,
            isp="ISP",
            punitive_eligible=True,
        )
        runtime = SimpleNamespace(
            settings={
                "dry_run": True,
                "shadow_mode": False,
                "warning_only_mode": False,
                "usage_time_threshold": 0,
                "ban_durations_minutes": [15, 60],
            }
        )

        with self.store._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            enforcement = ingest_pipeline._plan_enforcement_tx(
                conn,
                runtime,
                {"uuid": "uuid-dry-ban"},
                {"ip": "1.2.3.5", "tag": "SELFSTEAL_RU-YANDEX_TCP"},
                bundle,
                event_uid="dry-ban-1",
                analysis_event_id=1,
                review_case_id=None,
            )
            conn.commit()

        self.assertEqual(
            enforcement,
            {
                "type": "warning",
                "warning_count": 1,
                "warning_only": True,
                "delivery_status": "applied",
                "dry_run": True,
            },
        )
        self._assert_no_persisted_enforcement_state()

    def test_plan_enforcement_tx_warning_only_mode_does_not_persist_warning_state(self):
        bundle = DecisionBundle(
            ip="1.2.3.6",
            verdict="HOME",
            confidence_band="HIGH_HOME",
            score=-80,
            isp="ISP",
            punitive_eligible=True,
        )
        runtime = SimpleNamespace(
            settings={
                "dry_run": False,
                "shadow_mode": False,
                "warning_only_mode": True,
                "usage_time_threshold": 0,
                "ban_durations_minutes": [15, 60],
            }
        )

        with self.store._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            enforcement = ingest_pipeline._plan_enforcement_tx(
                conn,
                runtime,
                {"uuid": "uuid-warning-only"},
                {"ip": "1.2.3.6", "tag": "SELFSTEAL_RU-YANDEX_TCP"},
                bundle,
                event_uid="warning-only-1",
                analysis_event_id=1,
                review_case_id=None,
            )
            conn.commit()

        self.assertEqual(enforcement["type"], "warning")
        self.assertTrue(enforcement["warning_only"])
        self._assert_no_persisted_enforcement_state()

    def test_plan_enforcement_tx_is_suppressed_until_usage_threshold_is_reached(self):
        bundle = DecisionBundle(
            ip="1.2.3.66",
            verdict="HOME",
            confidence_band="HIGH_HOME",
            score=-80,
            isp="ISP",
            punitive_eligible=True,
        )
        runtime = SimpleNamespace(
            settings={
                "dry_run": False,
                "shadow_mode": False,
                "warning_only_mode": False,
                "usage_time_threshold": 900,
                "ban_durations_minutes": [15, 60],
            }
        )
        now = datetime.utcnow().replace(microsecond=0).isoformat()

        with self.store._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO active_trackers (key, start_time, last_seen) VALUES (?, ?, ?)",
                ("uuid-threshold:1.2.3.66", now, now),
            )
            enforcement = ingest_pipeline._plan_enforcement_tx(
                conn,
                runtime,
                {"uuid": "uuid-threshold"},
                {"ip": "1.2.3.66", "tag": "SELFSTEAL_RU-YANDEX_TCP"},
                bundle,
                event_uid="threshold-1",
                analysis_event_id=1,
                review_case_id=None,
            )
            conn.commit()

        self.assertEqual(enforcement["type"], "suppressed")
        self.assertEqual(enforcement["reason"], "usage_threshold")
        self.assertEqual(enforcement["required_seconds"], 900)
        self.assertLess(enforcement["elapsed_seconds"], 900)
        self._assert_no_persisted_enforcement_state()

    def test_dispatch_enforcement_jobs_are_suppressed_outside_enforce_mode(self):
        class FakeStore:
            def __init__(self):
                self.applied_ids: list[int] = []
                self.snapshot_dirty = False

            def claim_enforcement_jobs(self, owner: str, *, limit: int, claim_timeout_seconds: int):
                return [{"id": 17, "attempt_count": 0}]

            def get_live_rules_state(self):
                return {
                    "rules": {
                        "settings": {
                            "dry_run": False,
                            "shadow_mode": False,
                            "warning_only_mode": True,
                            "limiter_rollout_mode": "warning_only",
                        }
                    }
                }

            def mark_enforcement_job_applied(self, job_id: int) -> None:
                self.applied_ids.append(int(job_id))

            def mark_ingest_pipeline_snapshot_dirty(self) -> None:
                self.snapshot_dirty = True

        fake_store = FakeStore()
        container = SimpleNamespace(store=fake_store)

        with patch.object(
            ingest_pipeline,
            "_dispatch_remote_job",
            side_effect=AssertionError("remote dispatch must not run in warning-only mode"),
        ):
            summary = asyncio.run(ingest_pipeline.dispatch_enforcement_batch_once(container))

        self.assertEqual(summary["claimed"], 1)
        self.assertEqual(summary["applied"], 1)
        self.assertEqual(summary["retried"], 0)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(fake_store.applied_ids, [17])
        self.assertTrue(fake_store.snapshot_dirty)

    def test_plan_enforcement_tx_respects_limiter_rollout_modes(self):
        bundle = DecisionBundle(
            ip="1.2.3.9",
            verdict="HOME",
            confidence_band="HIGH_HOME",
            score=-120,
            isp="ISP",
            punitive_eligible=True,
        )
        runtime = SimpleNamespace(
            settings={
                "dry_run": False,
                "shadow_mode": False,
                "warning_only_mode": False,
                "usage_time_threshold": 0,
                "ban_durations_minutes": [15, 60],
                "limiter_enabled": True,
                "limiter_threshold_count": 1,
                "limiter_window_seconds": 3600,
                "limiter_rollout_mode": "observe",
            }
        )

        with self.store._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            suppressed = ingest_pipeline._plan_enforcement_tx(
                conn,
                runtime,
                {"uuid": "uuid-limiter-observe"},
                {"ip": "1.2.3.9", "tag": "SELFSTEAL_RU-YANDEX_TCP"},
                bundle,
                event_uid="limiter-observe-1",
                analysis_event_id=1,
                review_case_id=None,
            )
            conn.commit()
        self.assertEqual(suppressed["type"], "suppressed")
        self.assertEqual(suppressed["reason"], "rollout_observe")
        self.assertEqual(suppressed["limiter"]["rollout_mode"], "observe")

        runtime.settings["limiter_rollout_mode"] = "warning_only"
        with self.store._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            warning = ingest_pipeline._plan_enforcement_tx(
                conn,
                runtime,
                {"uuid": "uuid-limiter-warning"},
                {"ip": "1.2.3.10", "tag": "SELFSTEAL_RU-YANDEX_TCP"},
                bundle,
                event_uid="limiter-warning-1",
                analysis_event_id=2,
                review_case_id=None,
            )
            conn.commit()
        self.assertEqual(warning["type"], "warning")
        self.assertTrue(bool(warning["warning_only"]))
        self.assertEqual(warning["limiter"]["rollout_mode"], "warning_only")

    def test_apply_enforcement_if_needed_dry_run_warning_does_not_persist_warning_state(self):
        bundle = DecisionBundle(
            ip="1.2.3.6",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=-20,
            isp="ISP",
            punitive_eligible=True,
        )
        runtime = SimpleNamespace(
            container=self.container,
            remnawave_client=SimpleNamespace(enabled=True),
            settings={
                "dry_run": True,
                "shadow_mode": False,
                "warning_only_mode": False,
                "usage_time_threshold": 0,
                "ban_durations_minutes": [15, 60],
            },
        )

        enforcement = asyncio.run(
            module_service._apply_enforcement_if_needed(
                runtime,
                {"uuid": "uuid-module-dry-warning"},
                {"ip": "1.2.3.6", "tag": "SELFSTEAL_RU-YANDEX_TCP"},
                bundle,
            )
        )

        self.assertEqual(
            enforcement,
            {
                "type": "warning",
                "warning_count": 1,
                "warning_only": True,
                "dry_run": True,
            },
        )
        self._assert_no_persisted_enforcement_state()

    def test_apply_enforcement_if_needed_dry_run_returns_non_persistent_warning(self):
        bundle = DecisionBundle(
            ip="1.2.3.7",
            verdict="HOME",
            confidence_band="HIGH_HOME",
            score=-120,
            isp="ISP",
            punitive_eligible=True,
        )
        runtime = SimpleNamespace(
            container=self.container,
            remnawave_client=SimpleNamespace(enabled=True),
            settings={
                "dry_run": True,
                "shadow_mode": False,
                "warning_only_mode": False,
                "usage_time_threshold": 0,
                "ban_durations_minutes": [15, 60],
            },
        )

        enforcement = asyncio.run(
            module_service._apply_enforcement_if_needed(
                runtime,
                {"uuid": "uuid-module-dry-ban"},
                {"ip": "1.2.3.7", "tag": "SELFSTEAL_RU-YANDEX_TCP"},
                bundle,
            )
        )

        self.assertEqual(
            enforcement,
            {
                "type": "warning",
                "warning_count": 1,
                "warning_only": True,
                "dry_run": True,
            },
        )
        self._assert_no_persisted_enforcement_state()

    def test_apply_enforcement_if_needed_is_suppressed_until_usage_threshold_is_reached(self):
        bundle = DecisionBundle(
            ip="1.2.3.77",
            verdict="HOME",
            confidence_band="HIGH_HOME",
            score=-120,
            isp="ISP",
            punitive_eligible=True,
        )
        now = datetime.utcnow().replace(microsecond=0).isoformat()
        asyncio.run(
            self.analysis_store.execute(
                "INSERT INTO active_trackers (key, start_time, last_seen) VALUES (?, ?, ?)",
                ("uuid-module-threshold:1.2.3.77", now, now),
            )
        )
        runtime = SimpleNamespace(
            container=self.container,
            remnawave_client=SimpleNamespace(enabled=True),
            settings={
                "dry_run": False,
                "shadow_mode": False,
                "warning_only_mode": False,
                "usage_time_threshold": 900,
                "ban_durations_minutes": [15, 60],
            },
        )

        enforcement = asyncio.run(
            module_service._apply_enforcement_if_needed(
                runtime,
                {"uuid": "uuid-module-threshold"},
                {"ip": "1.2.3.77", "tag": "SELFSTEAL_RU-YANDEX_TCP"},
                bundle,
            )
        )

        self.assertEqual(enforcement["type"], "suppressed")
        self.assertEqual(enforcement["reason"], "usage_threshold")
        self.assertEqual(enforcement["required_seconds"], 900)
        self.assertLess(enforcement["elapsed_seconds"], 900)
        self._assert_no_persisted_enforcement_state()

    def test_event_batch_returns_503_when_storage_is_temporarily_busy(self):
        self.store.create_managed_module(
            "node-busy",
            "token-busy",
            "encrypted-token-busy",
            module_name="Busy Node",
            metadata={
                "inbound_tags": ["SELFSTEAL_RU-YANDEX_TCP"],
            },
        )
        module_service.register_module(
            self.container,
            {
                "module_id": "node-busy",
                "module_name": "Busy Node",
                "version": "1.0.0",
                "protocol_version": "v1",
            },
            "token-busy",
        )

        payload = EventBatchRequest(
            module_id="node-busy",
            protocol_version="v1",
            items=[
                {
                    "event_uid": "busy-1",
                    "occurred_at": "2026-04-11T12:00:00",
                    "ip": "1.2.3.4",
                    "tag": "SELFSTEAL_RU-YANDEX_TCP",
                    "uuid": "uuid-busy",
                }
            ],
        )

        with patch.object(self.store, "enqueue_raw_events", side_effect=sqlite3.OperationalError("database is locked")):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(
                    modules_router.module_events_batch(
                        payload,
                        authorization="Bearer token-busy",
                        container=self.container,
                    )
                )

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.detail, module_service.MODULE_INGEST_BUSY_DETAIL)

    def test_register_returns_503_when_storage_is_temporarily_busy(self):
        payload = modules_router.ModuleRegisterRequest(
            module_id="node-busy",
            module_name="Busy Node",
            version="1.0.0",
            protocol_version="v1",
        )

        with patch.object(self.store, "register_module", side_effect=sqlite3.OperationalError("database is locked")):
            with self.assertRaises(HTTPException) as ctx:
                modules_router.register_module(
                    payload,
                    authorization="Bearer token-busy",
                    container=self.container,
                )

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.detail, module_service.MODULE_INGEST_BUSY_DETAIL)

    def test_event_batch_builds_runtime_context_once(self):
        self.store.create_managed_module(
            "node-a",
            "token-a",
            "encrypted-token-a",
            module_name="Node A",
            metadata={
                "inbound_tags": ["SELFSTEAL_RU-YANDEX_TCP"],
            },
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

        original_builder = module_service._build_batch_context
        asyncio.run(
            module_service.ingest_module_events(
                self.container,
                {
                    "module_id": "node-a",
                    "protocol_version": "v1",
                    "items": [
                        {
                            "event_uid": "batch-1",
                            "occurred_at": "2026-04-11T12:00:00",
                            "ip": "1.2.3.4",
                            "tag": "SELFSTEAL_RU-YANDEX_TCP",
                            "uuid": "uuid-1",
                        },
                        {
                            "event_uid": "batch-2",
                            "occurred_at": "2026-04-11T12:00:01",
                            "ip": "1.2.3.5",
                            "tag": "SELFSTEAL_RU-YANDEX_TCP",
                            "uuid": "uuid-2",
                        },
                    ],
                },
                "token-a",
            )
        )

        async def fake_process(_container, _runtime, _module, _row):
            return {"status": "processed"}

        with patch.object(ingest_pipeline, "_process_claimed_event", side_effect=fake_process), patch.object(
            ingest_pipeline,
            "_build_batch_context",
            wraps=original_builder,
        ) as runtime_builder:
            result = asyncio.run(ingest_pipeline.process_ingest_batch_once(self.container))

        self.assertEqual(runtime_builder.call_count, 1)
        self.assertEqual(result["processed"], 2)

    def test_event_batch_real_processing_does_not_crash_when_recording_behavioral_decision(self):
        self.store.create_managed_module(
            "node-a",
            "token-a",
            "encrypted-token-a",
            module_name="Node A",
            metadata={
                "inbound_tags": ["SELFSTEAL_RU-YANDEX_TCP"],
            },
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

        class FakeIPInfo:
            async def get_ip_info(self, _ip):
                return {"org": "AS51547 Mobile Operator", "hostname": "mobile.example"}

            def parse_asn(self, value):
                return 51547 if value else None

            def normalize_isp_name(self, value):
                return str(value or "")

            def is_datacenter(self, _org, _hostname):
                return False

        with patch.object(module_service, "_ipinfo_client", return_value=FakeIPInfo()), patch.object(
            module_service,
            "_remnawave_client",
            return_value=SimpleNamespace(enabled=False, get_user_data=lambda _identifier: None),
        ):
            enqueue_result = asyncio.run(
                module_service.ingest_module_events(
                    self.container,
                    {
                        "module_id": "node-a",
                        "protocol_version": "v1",
                        "items": [
                            {
                                "event_uid": "live-1",
                                "occurred_at": "2026-04-11T12:00:00",
                                "ip": "1.2.3.4",
                                "tag": "SELFSTEAL_RU-YANDEX_TCP",
                                "uuid": "123e4567-e89b-12d3-a456-426614174000",
                            }
                        ],
                    },
                    "token-a",
                )
            )
            processed_result = asyncio.run(ingest_pipeline.process_ingest_batch_once(self.container))

        self.assertEqual(enqueue_result["accepted"], 1)
        self.assertEqual(enqueue_result["queued"], 1)
        self.assertEqual(processed_result["processed"], 1)
        with self.store._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM analysis_events WHERE source_event_uid = ?",
                ("live-1",),
            ).fetchone()
        self.assertEqual(row["cnt"], 1)

    def test_short_provider_conflict_cases_auto_resolve_on_ingest(self):
        self.store.create_managed_module(
            "node-auto",
            "token-auto",
            "encrypted-token-auto",
            module_name="Node Auto",
            metadata={"inbound_tags": ["SELFSTEAL_RU-YANDEX_TCP"]},
        )
        module_service.register_module(
            self.container,
            {
                "module_id": "node-auto",
                "module_name": "Node Auto",
                "version": "1.0.0",
                "protocol_version": "v1",
            },
            "token-auto",
        )

        asyncio.run(
            module_service.ingest_module_events(
                self.container,
                {
                    "module_id": "node-auto",
                    "protocol_version": "v1",
                    "items": [
                        {
                            "event_uid": "auto-review-1",
                            "occurred_at": "2026-04-11T12:00:00",
                            "ip": "1.2.3.44",
                            "tag": "SELFSTEAL_RU-YANDEX_TCP",
                            "uuid": "uuid-auto",
                        }
                    ],
                },
                "token-auto",
            )
        )

        bundle = DecisionBundle(
            ip="1.2.3.44",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=15,
            asn=12345,
            isp="MTS",
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "provider_classification": "mixed",
            "service_type_hint": "unknown",
            "service_conflict": False,
            "review_recommended": True,
        }

        async def fake_resolve_user(_runtime, payload):
            return {
                "uuid": payload.get("uuid"),
                "username": "alice",
                "telegramId": "1001",
                "id": 42,
            }

        async def fake_analyze_event(*args, **kwargs):
            return bundle

        runtime = SimpleNamespace(settings={}, exempt_ids=frozenset(), exempt_tg_ids=frozenset())

        with patch.object(ingest_pipeline, "_build_batch_context", return_value=runtime), patch.object(
            ingest_pipeline,
            "_resolve_remote_user",
            side_effect=fake_resolve_user,
        ), patch.object(
            ingest_pipeline,
            "_analyze_event",
            side_effect=fake_analyze_event,
        ):
            processed_result = asyncio.run(ingest_pipeline.process_ingest_batch_once(self.container))

        self.assertEqual(processed_result["processed"], 1)
        detail = self.store.get_review_case(1)
        self.assertEqual(detail["status"], "RESOLVED")
        self.assertEqual(detail["verdict"], "UNSURE")
        self.assertEqual(detail["resolutions"][0]["resolution"], "MOBILE")
        self.assertEqual(detail["resolutions"][0]["actor"], "system:auto-review")
        self.assertIn("mobile_short_provider_conflict", detail["resolutions"][0]["note"])
        self.assertIn("precision=0.991", detail["resolutions"][0]["note"])
        self.assertEqual(self.store.get_ip_override("1.2.3.44"), "MOBILE")

    def test_event_batch_tolerates_none_runtime_settings_values(self):
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        payload.setdefault("settings", {})
        payload["settings"]["pure_asn_score"] = None
        payload["settings"]["mixed_asn_score"] = None
        self.config_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        self.store.sync_runtime_config(payload)

        self.store.create_managed_module(
            "node-b",
            "token-b",
            "encrypted-token-b",
            module_name="Node B",
            metadata={"inbound_tags": ["SELFSTEAL_RU-YANDEX_TCP"]},
        )
        module_service.register_module(
            self.container,
            {
                "module_id": "node-b",
                "module_name": "Node B",
                "version": "1.0.0",
                "protocol_version": "v1",
            },
            "token-b",
        )

        with patch.object(ingest_pipeline, "_process_claimed_event", wraps=ingest_pipeline._process_claimed_event):
            enqueue_result = asyncio.run(
                module_service.ingest_module_events(
                    self.container,
                    {
                        "module_id": "node-b",
                        "protocol_version": "v1",
                        "items": [
                            {
                                "event_uid": "none-settings-1",
                                "occurred_at": "2026-04-11T12:00:00",
                                "ip": "1.2.3.9",
                                "tag": "SELFSTEAL_RU-YANDEX_TCP",
                                "uuid": "uuid-9",
                            }
                        ],
                    },
                    "token-b",
                )
            )
            processed_result = asyncio.run(ingest_pipeline.process_ingest_batch_once(self.container))

        self.assertEqual(enqueue_result["accepted"], 1)
        self.assertEqual(processed_result["processed"], 1)

    def test_event_batch_persists_optional_client_fields_and_geo_context(self):
        self.store.create_managed_module(
            "node-c",
            "token-c",
            "encrypted-token-c",
            module_name="Node C",
            metadata={"inbound_tags": ["SELFSTEAL_RU-YANDEX_TCP"]},
        )
        module_service.register_module(
            self.container,
            {
                "module_id": "node-c",
                "module_name": "Node C",
                "version": "1.0.0",
                "protocol_version": "v1",
            },
            "token-c",
        )

        class FakeIPInfo:
            async def get_ip_info(self, _ip):
                return {
                    "org": "AS51547 Mobile Operator",
                    "hostname": "mobile.example",
                    "country": "RU",
                    "region": "Moscow",
                    "city": "Moscow",
                    "loc": "55.75,37.61",
                }

            def parse_asn(self, value):
                return 51547 if value else None

            def normalize_isp_name(self, value):
                return str(value or "")

            def is_datacenter(self, _org, _hostname):
                return False

        with patch.object(module_service, "_ipinfo_client", return_value=FakeIPInfo()), patch.object(
            module_service,
            "_remnawave_client",
            return_value=SimpleNamespace(enabled=False, get_user_data=lambda _identifier: None),
        ):
            enqueue_result = asyncio.run(
                module_service.ingest_module_events(
                    self.container,
                    {
                        "module_id": "node-c",
                        "protocol_version": "v1",
                        "items": [
                            {
                                "event_uid": "usage-1",
                                "occurred_at": "2026-04-11T12:00:00",
                                "ip": "1.2.3.4",
                                "tag": "SELFSTEAL_RU-YANDEX_TCP",
                                "uuid": "123e4567-e89b-12d3-a456-426614174000",
                                "client_device_id": "dev-1",
                                "client_device_label": "Pixel 8",
                                "client_os_family": "Android",
                                "client_os_version": "15",
                                "client_app_name": "Happ",
                                "client_app_version": "1.2.3",
                            }
                        ],
                    },
                    "token-c",
                )
            )
            processed_result = asyncio.run(ingest_pipeline.process_ingest_batch_once(self.container))

        self.assertEqual(enqueue_result["accepted"], 1)
        self.assertEqual(processed_result["processed"], 1)
        with self.store._connect() as conn:
            row = conn.execute(
                """
                SELECT country, region, city, loc,
                       client_device_id, client_device_label, client_os_family,
                       client_os_version, client_app_name, client_app_version
                FROM analysis_events
                WHERE source_event_uid = ?
                """,
                ("usage-1",),
            ).fetchone()

        self.assertEqual(row["country"], "RU")
        self.assertEqual(row["region"], "Moscow")
        self.assertEqual(row["city"], "Moscow")
        self.assertEqual(row["loc"], "55.75,37.61")
        self.assertEqual(row["client_device_id"], "dev-1")
        self.assertEqual(row["client_device_label"], "Pixel 8")
        self.assertEqual(row["client_os_family"], "Android")
        self.assertEqual(row["client_os_version"], "15")
        self.assertEqual(row["client_app_name"], "Happ")
        self.assertEqual(row["client_app_version"], "1.2.3")


if __name__ == "__main__":
    unittest.main()
