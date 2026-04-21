from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mobguard_platform import AnalysisStore, PlatformStore
from scripts import db_maintenance as db_maintenance_script


class DatabaseMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-maintenance-")
        self.runtime_dir = Path(self.temp_dir) / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.runtime_dir / "bans.db"
        self.config_path = self.runtime_dir / "config.json"
        self.base_config = {
            "_meta": {
                "revision": 3,
                "updated_at": "2026-04-20T12:00:00",
                "updated_by": "test",
            },
            "settings": {
                "db_cleanup_interval_minutes": 30,
                "module_heartbeats_retention_days": 14,
                "ingested_raw_events_retention_days": 30,
                "ip_history_retention_days": 30,
                "orphan_analysis_events_retention_days": 30,
                "resolved_review_retention_days": 90,
                "subnet_mobile_ttl_days": 45,
                "subnet_home_ttl_days": 15,
                "review_ui_base_url": "https://mobguard.example.com",
            },
            "provider_profiles": [],
            "mixed_asns": [],
            "pure_mobile_asns": [],
            "pure_home_asns": [],
            "allowed_isp_keywords": [],
            "home_isp_keywords": [],
            "exclude_isp_keywords": [],
            "admin_tg_ids": [],
            "exempt_ids": [],
            "exempt_tg_ids": [],
        }
        self.config_path.write_text(json.dumps(self.base_config, ensure_ascii=False, indent=2), encoding="utf-8")
        self.analysis_store = AnalysisStore(str(self.db_path))
        self.store = PlatformStore(str(self.db_path), self.base_config, str(self.config_path))
        self.analysis_store.init_schema()
        self.store.init_schema()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _insert_analysis_event(self, conn: sqlite3.Connection, *, created_at: str, ip: str) -> int:
        cursor = conn.execute(
            """
            INSERT INTO analysis_events (
                created_at, module_id, module_name, uuid, username, system_id, telegram_id, ip, tag,
                verdict, confidence_band, score, isp, asn, punitive_eligible,
                reasons_json, signal_flags_json, bundle_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                "node-a",
                "Node A",
                "uuid-1",
                "alice",
                42,
                "1001",
                ip,
                "TAG",
                "HOME",
                "PROBABLE_HOME",
                18,
                "ISP",
                12345,
                0,
                "[]",
                "{}",
                "{}",
            ),
        )
        return int(cursor.lastrowid)

    def test_run_db_maintenance_prunes_stale_rows_and_keeps_open_review_state(self):
        now_utc = datetime.utcnow().replace(microsecond=0)
        now_local = datetime.now().replace(microsecond=0)
        stale_review_time = (now_utc - timedelta(days=120)).isoformat()
        fresh_review_time = (now_utc - timedelta(days=3)).isoformat()
        stale_local_time = (now_local - timedelta(days=60)).isoformat()
        fresh_local_time = now_local.isoformat()

        with self.store._connect() as conn:
            conn.execute(
                "INSERT INTO active_trackers (key, start_time, last_seen) VALUES (?, ?, ?)",
                ("uuid-1:10.0.0.1", stale_local_time, stale_local_time),
            )
            conn.execute(
                "INSERT INTO active_trackers (key, start_time, last_seen) VALUES (?, ?, ?)",
                ("uuid-1:10.0.0.2", fresh_local_time, fresh_local_time),
            )
            conn.execute(
                """
                INSERT INTO ip_decisions (ip, status, confidence, details, asn, expires, log_json, bundle_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("10.0.0.10", "HOME", "HIGH", "ISP", 12345, stale_local_time, "[]", "{}"),
            )
            conn.execute(
                """
                INSERT INTO ip_decisions (ip, status, confidence, details, asn, expires, log_json, bundle_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "10.0.0.11",
                    "HOME",
                    "HIGH",
                    "ISP",
                    12345,
                    (now_local + timedelta(days=2)).isoformat(),
                    "[]",
                    "{}",
                ),
            )
            conn.execute(
                "INSERT INTO unsure_patterns (ip_pattern, decision, timestamp) VALUES (?, ?, ?)",
                ("10.0.0.12", "HOME", stale_local_time),
            )
            conn.execute(
                "INSERT INTO unsure_patterns (ip_pattern, decision, timestamp) VALUES (?, ?, ?)",
                ("10.0.0.13", "HOME", fresh_local_time),
            )
            conn.execute(
                """
                INSERT INTO daily_stats (stat_type, stat_key, sub_key, value, date)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("asn", "12345", "", 1, (now_local - timedelta(days=20)).strftime("%Y-%m-%d")),
            )
            conn.execute(
                """
                INSERT INTO daily_stats (stat_type, stat_key, sub_key, value, date)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("asn", "12345", "", 2, now_local.strftime("%Y-%m-%d")),
            )
            conn.execute(
                """
                INSERT INTO exact_ip_overrides (
                    ip, decision, source, actor, actor_tg_id, created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("10.0.0.14", "HOME", "review_resolution", "admin", 1001, stale_review_time, stale_review_time, stale_review_time),
            )
            conn.execute(
                """
                INSERT INTO exact_ip_overrides (
                    ip, decision, source, actor, actor_tg_id, created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "10.0.0.15",
                    "HOME",
                    "review_resolution",
                    "admin",
                    1001,
                    fresh_review_time,
                    fresh_review_time,
                    (now_utc + timedelta(days=5)).isoformat(),
                ),
            )
            conn.execute(
                """
                INSERT INTO admin_sessions (token, telegram_id, username, first_name, payload_json, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("expired-session", 1001, "admin", "Admin", "{}", stale_review_time, stale_review_time),
            )
            conn.execute(
                """
                INSERT INTO admin_sessions (token, telegram_id, username, first_name, payload_json, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "active-session",
                    1001,
                    "admin",
                    "Admin",
                    "{}",
                    fresh_review_time,
                    (now_utc + timedelta(days=5)).isoformat(),
                ),
            )
            conn.execute(
                """
                INSERT INTO module_heartbeats (
                    module_id, status, version, protocol_version, config_revision_applied, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("node-a", "online", "1.0.0", "v1", 1, json.dumps({"stale": True}), stale_review_time),
            )
            conn.execute(
                """
                INSERT INTO module_heartbeats (
                    module_id, status, version, protocol_version, config_revision_applied, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("node-a", "online", "1.0.1", "v1", 1, json.dumps({"stale": False}), fresh_review_time),
            )
            conn.execute(
                """
                INSERT INTO ingested_raw_events (
                    event_uid, module_id, module_name, occurred_at, log_offset, subject_uuid, username,
                    system_id, telegram_id, ip, tag, raw_payload_json, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "old-event",
                    "node-a",
                    "Node A",
                    stale_review_time,
                    1,
                    "uuid-1",
                    "alice",
                    42,
                    "1001",
                    "10.0.0.20",
                    "TAG",
                    json.dumps({"payload": "x" * 512}),
                    stale_review_time,
                ),
            )
            conn.execute(
                """
                INSERT INTO ingested_raw_events (
                    event_uid, module_id, module_name, occurred_at, log_offset, subject_uuid, username,
                    system_id, telegram_id, ip, tag, raw_payload_json, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "new-event",
                    "node-a",
                    "Node A",
                    fresh_review_time,
                    2,
                    "uuid-1",
                    "alice",
                    42,
                    "1001",
                    "10.0.0.21",
                    "TAG",
                    json.dumps({"payload": "fresh"}),
                    fresh_review_time,
                ),
            )
            conn.execute(
                "INSERT INTO ip_history (uuid, ip, timestamp) VALUES (?, ?, ?)",
                ("uuid-1", "10.0.0.30", stale_local_time),
            )
            conn.execute(
                "INSERT INTO ip_history (uuid, ip, timestamp) VALUES (?, ?, ?)",
                ("uuid-1", "10.0.0.31", fresh_local_time),
            )
            conn.execute(
                """
                INSERT INTO subnet_evidence (subnet, mobile_count, home_count, last_updated)
                VALUES (?, ?, ?, ?)
                """,
                ("10.0.0", 2, 0, stale_local_time),
            )
            conn.execute(
                """
                INSERT INTO subnet_evidence (subnet, mobile_count, home_count, last_updated)
                VALUES (?, ?, ?, ?)
                """,
                ("10.0.1", 1, 0, fresh_local_time),
            )
            conn.execute(
                """
                INSERT INTO violation_history (uuid, ip, isp, asn, tag, strike_number, punishment_duration, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("uuid-1", "10.0.0.40", "ISP", 12345, "TAG", 1, 60, stale_review_time),
            )
            conn.execute(
                """
                INSERT INTO violation_history (uuid, ip, isp, asn, tag, strike_number, punishment_duration, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("uuid-1", "10.0.0.41", "ISP", 12345, "TAG", 2, 60, fresh_review_time),
            )

            open_event_id = self._insert_analysis_event(conn, created_at=fresh_review_time, ip="10.0.0.50")
            stale_case_event_id = self._insert_analysis_event(conn, created_at=stale_review_time, ip="10.0.0.51")
            orphan_old_event_id = self._insert_analysis_event(conn, created_at=stale_review_time, ip="10.0.0.52")
            orphan_new_event_id = self._insert_analysis_event(conn, created_at=fresh_review_time, ip="10.0.0.53")

            open_case_id = conn.execute(
                """
                INSERT INTO review_cases (
                    unique_key, status, review_reason, module_id, module_name, uuid, username, system_id, telegram_id,
                    ip, tag, verdict, confidence_band, score, isp, asn, punitive_eligible, latest_event_id,
                    repeat_count, reason_codes_json, opened_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "open-case",
                    "OPEN",
                    "probable_home",
                    "node-a",
                    "Node A",
                    "uuid-1",
                    "alice",
                    42,
                    "1001",
                    "10.0.0.50",
                    "TAG",
                    "HOME",
                    "PROBABLE_HOME",
                    18,
                    "ISP",
                    12345,
                    0,
                    open_event_id,
                    1,
                    '["probable_home"]',
                    fresh_review_time,
                    fresh_review_time,
                ),
            ).lastrowid
            stale_case_id = conn.execute(
                """
                INSERT INTO review_cases (
                    unique_key, status, review_reason, module_id, module_name, uuid, username, system_id, telegram_id,
                    ip, tag, verdict, confidence_band, score, isp, asn, punitive_eligible, latest_event_id,
                    repeat_count, reason_codes_json, opened_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "resolved-case",
                    "RESOLVED",
                    "probable_home",
                    "node-a",
                    "Node A",
                    "uuid-1",
                    "alice",
                    42,
                    "1001",
                    "10.0.0.51",
                    "TAG",
                    "HOME",
                    "PROBABLE_HOME",
                    18,
                    "ISP",
                    12345,
                    0,
                    stale_case_event_id,
                    1,
                    '["probable_home"]',
                    stale_review_time,
                    stale_review_time,
                ),
            ).lastrowid
            conn.execute(
                """
                INSERT INTO review_resolutions (case_id, event_id, resolution, actor, actor_tg_id, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (stale_case_id, stale_case_event_id, "HOME", "admin", 1001, "confirmed", stale_review_time),
            )
            conn.execute(
                """
                INSERT INTO review_labels (case_id, event_id, pattern_type, pattern_value, decision, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (stale_case_id, stale_case_event_id, "asn", "12345", "HOME", stale_review_time),
            )
            conn.commit()

        report = self.store.run_db_maintenance(mode="periodic")

        self.assertEqual(report["deleted"]["active_trackers"], 1)
        self.assertEqual(report["deleted"]["ip_decisions"], 1)
        self.assertEqual(report["deleted"]["unsure_patterns"], 1)
        self.assertEqual(report["deleted"]["daily_stats"], 1)
        self.assertEqual(report["deleted"]["exact_ip_overrides"], 1)
        self.assertEqual(report["deleted"]["admin_sessions"], 1)
        self.assertEqual(report["deleted"]["module_heartbeats"], 1)
        self.assertEqual(report["deleted"]["ingested_raw_events"], 1)
        self.assertEqual(report["deleted"]["ip_history"], 1)
        self.assertEqual(report["deleted"]["subnet_evidence"], 1)
        self.assertEqual(report["deleted"]["violation_history"], 1)
        self.assertEqual(report["deleted"]["review_resolutions"], 1)
        self.assertEqual(report["deleted"]["review_labels"], 1)
        self.assertEqual(report["deleted"]["review_cases"], 1)
        self.assertEqual(report["deleted"]["analysis_events_from_cases"], 1)
        self.assertEqual(report["deleted"]["orphan_analysis_events"], 1)
        self.assertFalse(report["vacuumed"])

        with self.store._connect() as conn:
            remaining_case_statuses = {
                row["status"]
                for row in conn.execute("SELECT status FROM review_cases").fetchall()
            }
            self.assertEqual(remaining_case_statuses, {"OPEN"})
            remaining_review_case = conn.execute(
                "SELECT id, latest_event_id FROM review_cases WHERE id = ?",
                (open_case_id,),
            ).fetchone()
            self.assertIsNotNone(remaining_review_case)
            self.assertEqual(int(remaining_review_case["latest_event_id"]), open_event_id)
            analysis_event_ids = {
                int(row["id"])
                for row in conn.execute("SELECT id FROM analysis_events").fetchall()
            }
            self.assertIn(open_event_id, analysis_event_ids)
            self.assertIn(orphan_new_event_id, analysis_event_ids)
            self.assertNotIn(stale_case_event_id, analysis_event_ids)
            self.assertNotIn(orphan_old_event_id, analysis_event_ids)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS cnt FROM review_resolutions").fetchone()["cnt"],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS cnt FROM review_labels").fetchone()["cnt"],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS cnt FROM module_heartbeats").fetchone()["cnt"],
                1,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS cnt FROM ingested_raw_events").fetchone()["cnt"],
                1,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS cnt FROM ip_history").fetchone()["cnt"],
                1,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS cnt FROM violation_history").fetchone()["cnt"],
                1,
            )

    def test_emergency_script_runs_checkpoint_and_vacuum(self):
        stale_time = (datetime.utcnow().replace(microsecond=0) - timedelta(days=120)).isoformat()
        with self.store._connect() as conn:
            for index in range(32):
                conn.execute(
                    """
                    INSERT INTO module_heartbeats (
                        module_id, status, version, protocol_version, config_revision_applied, details_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "node-a",
                        "online",
                        "1.0.0",
                        "v1",
                        1,
                        json.dumps({"payload": "x" * 2048, "index": index}),
                        stale_time,
                    ),
                )
            conn.commit()

        with patch.dict(os.environ, {"BAN_SYSTEM_DIR": str(self.runtime_dir)}, clear=False):
            payload = db_maintenance_script.run("emergency")

        self.assertTrue(payload["report"]["vacuumed"])
        self.assertGreater(payload["report"]["deleted"]["module_heartbeats"], 0)
        before_total = payload["before"]["db_size_bytes"] + payload["before"]["wal_size_bytes"]
        after_total = payload["after"]["db_size_bytes"] + payload["after"]["wal_size_bytes"]
        self.assertLessEqual(after_total, before_total)

        with sqlite3.connect(payload["after"]["db_path"]) as conn:
            row = conn.execute("SELECT COUNT(*) FROM live_rules").fetchone()
        self.assertEqual(int(row[0]), 1)


if __name__ == "__main__":
    unittest.main()
