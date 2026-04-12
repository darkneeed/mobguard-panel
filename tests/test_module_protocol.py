import asyncio
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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
                "host": "node-a.example.com",
                "port": 2222,
                "access_log_path": "/var/log/remnanode/access.log",
                "config_profiles": ["Default-Profile"],
                "provider": "hetzner",
                "notes": "",
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

        heartbeat = module_service.record_module_heartbeat(
            self.container,
            {
                "module_id": "node-a",
                "status": "online",
                "version": "1.0.1",
                "protocol_version": "v1",
                "config_revision_applied": 3,
            },
            "token-a",
        )
        self.assertEqual(heartbeat["desired_config_revision"], 3)

        payload = module_service.list_modules(self.container)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["module_name"], "Node A")

    def test_event_batch_deduplicates_by_event_uid(self):
        self.store.create_managed_module(
            "node-a",
            "token-a",
            "encrypted-token-a",
            module_name="Node A",
            metadata={
                "host": "node-a.example.com",
                "port": 2222,
                "access_log_path": "/var/log/remnanode/access.log",
                "config_profiles": ["Default-Profile"],
                "provider": "",
                "notes": "",
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

        async def fake_process(container, module, payload):
            return {
                "status": "processed",
                "event_id": 101,
                "review_case_id": 202,
                "bundle": {"ip": payload["ip"]},
                "review_reason": None,
                "enforcement": None,
            }

        with patch.object(module_service, "_process_module_event", fake_process):
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
        self.assertEqual(result["processed"], 1)


if __name__ == "__main__":
    unittest.main()
