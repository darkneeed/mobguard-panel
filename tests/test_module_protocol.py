import asyncio
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from api.routers import modules as modules_router
from api.schemas.modules import EventBatchRequest
from api.services import ingest_pipeline
from api.services import modules as module_service
from mobguard_platform import AnalysisStore, PlatformStore


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
