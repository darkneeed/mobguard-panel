import os
import json
import shutil
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from mobguard_platform.models import DecisionBundle
from mobguard_platform.store import PlatformStore, ReadSnapshotUnavailableError


class StoreReviewFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-store-")
        self.db_path = os.path.join(self.temp_dir, "test.sqlite3")
        self.runtime_dir = os.path.join(self.temp_dir, "runtime")
        os.makedirs(self.runtime_dir, exist_ok=True)
        self.config_path = os.path.join(self.runtime_dir, "config.json")
        self.base_config = {
            "mixed_asns": [12345],
            "allowed_isp_keywords": ["mobile"],
            "home_isp_keywords": ["fiber"],
            "exclude_isp_keywords": ["hosting"],
            "provider_profiles": [
                {
                    "key": "mts",
                    "classification": "mixed",
                    "aliases": ["mts", "mgts"],
                    "mobile_markers": ["mobile", "lte"],
                    "home_markers": ["fiber", "gpon"],
                    "asns": [12345],
                }
            ],
            "admin_tg_ids": [1001],
            "exempt_tg_ids": [2002],
            "exempt_ids": [3003],
            "mobile_tags": ["TAG"],
            "settings": {
                "mobile_score_threshold": 55,
                "threshold_mobile": 60,
                "threshold_home": 15,
                "threshold_probable_home": 30,
                "threshold_probable_mobile": 50,
                "history_lookback_days": 14,
                "history_min_gap_minutes": 30,
                "history_mobile_same_subnet_min_distinct_ips": 8,
                "history_mobile_bonus": 40,
                "history_home_same_ip_min_records": 5,
                "history_home_same_ip_min_span_hours": 24,
                "history_home_penalty": -25,
                "provider_mobile_marker_bonus": 18,
                "provider_home_marker_penalty": -18,
                "provider_conflict_review_only": True,
                "learning_promote_asn_min_support": 1,
                "learning_promote_asn_min_precision": 1.0,
                "learning_promote_combo_min_support": 1,
                "learning_promote_combo_min_precision": 1.0,
                "shadow_mode": True,
                "log_file": "/var/log/remnanode/access.log",
                "review_ui_base_url": "https://mobguard.example.com",
            },
        }
        self.store = PlatformStore(self.db_path, self.base_config, self.config_path)
        self.store.init_schema()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_review_roundtrip_creates_override_and_pattern(self):
        bundle = DecisionBundle(
            ip="10.10.10.10",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=18,
            asn=12345,
            isp="ISP",
        )
        bundle.add_reason(
            "keyword_home",
            "generic_keyword",
            -20,
            "soft",
            "HOME",
            "keyword matched",
            {"keywords": ["fiber"]},
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "provider_classification": "mixed",
            "service_type_hint": "home",
            "service_conflict": False,
            "review_recommended": True,
        }
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        summary = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "probable_home")
        resolved = self.store.resolve_review_case(summary.id, "HOME", "admin", 1001, "confirmed")

        self.assertEqual(resolved["status"], "RESOLVED")
        self.assertEqual(resolved["system_id"], 42)
        self.assertEqual(resolved["latest_event"]["system_id"], 42)
        self.assertEqual(self.store.get_ip_override(bundle.ip), "HOME")
        self.assertIn("usage_profile_summary", resolved)
        self.assertGreaterEqual(int(resolved["usage_profile_signal_count"]), 0)
        self.assertGreaterEqual(int(resolved["usage_profile_priority"]), 0)
        pattern = self.store.get_promoted_pattern("asn", "12345")
        self.assertIsNotNone(pattern)
        self.assertEqual(pattern["decision"], "HOME")
        provider_pattern = self.store.get_promoted_pattern("provider", "mts")
        self.assertIsNotNone(provider_pattern)
        self.assertEqual(provider_pattern["decision"], "HOME")
        provider_service_pattern = self.store.get_promoted_pattern("provider_service", "mts:home")
        self.assertIsNotNone(provider_service_pattern)
        self.assertEqual(provider_service_pattern["decision"], "HOME")

    def test_skip_resolution_does_not_create_override_or_learning_and_case_reopens_on_new_event(self):
        bundle = DecisionBundle(
            ip="10.10.10.11",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="MTS",
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "provider_classification": "mixed",
            "service_type_hint": "conflict",
            "service_conflict": True,
            "review_recommended": True,
        }
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42, "module_id": "node-a", "module_name": "Node A"}
        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        summary = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "provider_conflict")

        skipped = self.store.resolve_review_case(summary.id, "SKIP", "admin", 1001, "need more data")

        self.assertEqual(skipped["status"], "SKIPPED")
        self.assertIsNone(self.store.get_ip_override(bundle.ip))
        self.assertIsNone(self.store.get_promoted_pattern("asn", "12345"))
        with self.store._connect() as conn:
            labels = conn.execute(
                "SELECT COUNT(*) AS cnt FROM review_labels WHERE case_id = ?",
                (summary.id,),
            ).fetchone()
            self.assertEqual(labels["cnt"], 0)

        next_bundle = DecisionBundle(
            ip="10.10.10.11",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=18,
            asn=12345,
            isp="MTS Fiber",
        )
        next_event_id = self.store.record_analysis_event(user, next_bundle.ip, "TAG", next_bundle)
        reopened = self.store.ensure_review_case(user, next_bundle.ip, "TAG", next_bundle, next_event_id, "probable_home")

        self.assertEqual(reopened.id, summary.id)
        self.assertEqual(reopened.status, "OPEN")
        self.assertEqual(reopened.repeat_count, 1)

    def test_repeat_count_requires_minimum_gap_between_hits(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        bundle = DecisionBundle(
            ip="10.10.10.15",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-A",
        )

        first_event = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        with self.store._connect() as conn:
            conn.execute("UPDATE analysis_events SET created_at = ? WHERE id = ?", ("2026-04-01T10:00:00", first_event))
            conn.commit()
        summary = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, first_event, "unsure")

        second_event = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        with self.store._connect() as conn:
            conn.execute("UPDATE analysis_events SET created_at = ? WHERE id = ?", ("2026-04-01T10:04:00", second_event))
            conn.commit()
        second_summary = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, second_event, "unsure")

        third_event = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        with self.store._connect() as conn:
            conn.execute("UPDATE analysis_events SET created_at = ? WHERE id = ?", ("2026-04-01T10:10:00", third_event))
            conn.commit()
        third_summary = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, third_event, "unsure")

        self.assertEqual(summary.id, second_summary.id)
        self.assertEqual(second_summary.repeat_count, 1)
        self.assertEqual(third_summary.repeat_count, 2)

    def test_repeat_count_increments_at_exactly_five_minutes(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        bundle = DecisionBundle(
            ip="10.10.10.16",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-A",
        )

        first_event = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        with self.store._connect() as conn:
            conn.execute("UPDATE analysis_events SET created_at = ? WHERE id = ?", ("2026-04-01T10:00:00", first_event))
            conn.commit()
        first_summary = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, first_event, "unsure")

        second_event = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        with self.store._connect() as conn:
            conn.execute("UPDATE analysis_events SET created_at = ? WHERE id = ?", ("2026-04-01T10:05:00", second_event))
            conn.commit()
        second_summary = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, second_event, "unsure")

        self.assertEqual(first_summary.id, second_summary.id)
        self.assertEqual(second_summary.repeat_count, 2)

    def test_compact_review_listing_skips_heavy_history_payloads(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42, "module_id": "node-a", "module_name": "Node A"}
        bundle = DecisionBundle(
            ip="10.10.10.17",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-A",
        )

        first_event = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, first_event, "unsure")
        second_bundle = DecisionBundle(
            ip="10.10.10.18",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-B",
        )
        second_event = self.store.record_analysis_event(user, second_bundle.ip, "TAG", second_bundle)
        self.store.ensure_review_case(user, second_bundle.ip, "TAG", second_bundle, second_event, "unsure")

        listing = self.store.list_review_cases({"status": "OPEN", "view": "compact", "page": 1, "page_size": 25})

        self.assertEqual(listing["count"], 2)
        item = listing["items"][0]
        self.assertTrue(item["ip_inventory"])
        self.assertEqual(item["module_inventory"], [])
        self.assertEqual(item["module_count"], 0)
        self.assertEqual(item["same_device_ip_history"], [])
        self.assertFalse(item["shared_account_suspected"])

    def test_overview_uses_teasers_without_full_review_listing(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        bundle = DecisionBundle(
            ip="10.10.10.19",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-A",
        )
        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "unsure")

        with patch.object(self.store.review_admin, "list_review_cases", side_effect=AssertionError("full listing should not be used")):
            overview = self.store.get_overview_metrics()

        self.assertEqual(overview["quality"]["open_cases"], 1)
        self.assertEqual(len(overview["latest_cases"]["items"]), 1)
        self.assertEqual(overview["latest_cases"]["items"][0]["ip"], bundle.ip)

    def test_recheck_review_case_can_auto_resolve_when_manual_review_is_no_longer_needed(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42, "module_id": "node-a", "module_name": "Node A"}
        original_bundle = DecisionBundle(
            ip="10.10.10.12",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=18,
            asn=12345,
            isp="MTS",
        )
        original_bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "provider_classification": "mixed",
            "service_type_hint": "unknown",
            "service_conflict": False,
            "review_recommended": True,
        }
        event_id = self.store.record_analysis_event(user, original_bundle.ip, "TAG", original_bundle)
        summary = self.store.ensure_review_case(user, original_bundle.ip, "TAG", original_bundle, event_id, "provider_conflict")

        refreshed_bundle = DecisionBundle(
            ip="10.10.10.12",
            verdict="MOBILE",
            confidence_band="HIGH_MOBILE",
            score=72,
            asn=12345,
            isp="MTS",
        )
        refreshed_bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "provider_classification": "mixed",
            "service_type_hint": "unknown",
            "service_conflict": False,
            "review_recommended": False,
        }
        refreshed_bundle.add_reason(
            "behavior_history_mobile",
            "behavior",
            40,
            "soft",
            "MOBILE",
            "Historical subnet rotation",
            {"subnet": "188.120.1", "distinct_ips": 9},
        )
        refreshed_bundle.add_reason(
            "learning_provider",
            "learning",
            6,
            "soft",
            "MOBILE",
            "Promoted provider pattern mts",
            {"pattern_type": "provider", "pattern_value": "mts", "support": 12, "precision": 1.0},
        )

        updated = self.store.recheck_review_case(
            summary.id,
            user,
            refreshed_bundle.ip,
            "TAG",
            refreshed_bundle,
            None,
            "system",
            1001,
            "auto recheck",
        )

        self.assertEqual(updated["status"], "RESOLVED")
        self.assertEqual(updated["verdict"], "MOBILE")
        self.assertEqual(updated["confidence_band"], "HIGH_MOBILE")
        self.assertEqual(updated["latest_event"]["verdict"], "MOBILE")
        self.assertIn("behavior_history_mobile", updated["reason_codes"])
        self.assertEqual(updated["resolutions"][0]["resolution"], "MOBILE")
        self.assertEqual(self.store.get_ip_override(refreshed_bundle.ip), "MOBILE")

    def test_live_rules_revision_conflict_is_rejected(self):
        state = self.store.get_live_rules_state()
        updated = self.store.update_live_rules(
            {"settings": {"threshold_mobile": 70}},
            "admin",
            1001,
            expected_revision=state["revision"],
            expected_updated_at=state["updated_at"],
        )
        self.assertEqual(updated["revision"], state["revision"] + 1)

        with self.assertRaises(ValueError):
            self.store.update_live_rules(
                {"settings": {"threshold_mobile": 80}},
                "admin",
                1001,
                expected_revision=state["revision"],
                expected_updated_at=state["updated_at"],
            )

        with open(self.config_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["settings"]["threshold_mobile"], 70)
        self.assertEqual(payload["_meta"]["revision"], updated["revision"])
        self.assertEqual(payload["settings"]["log_file"], "/var/log/remnanode/access.log")
        self.assertEqual(payload["mobile_tags"], ["TAG"])
        self.assertEqual(payload["settings"]["db_file"], "runtime/bans.db")
        self.assertEqual(payload["settings"]["geoip_db"], "runtime/GeoLite2-ASN.mmdb")

    def test_legacy_threshold_alias_is_normalized_in_saved_rules(self):
        updated = self.store.update_live_rules(
            {"settings": {"mobile_score_threshold": 72}},
            "admin",
            1001,
        )

        self.assertEqual(updated["rules"]["settings"]["threshold_mobile"], 72)
        with open(self.config_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["settings"]["threshold_mobile"], 72)
        self.assertNotIn("mobile_score_threshold", payload["settings"])

    def test_admin_and_exempt_lists_stay_separate(self):
        state = self.store.get_live_rules_state()

        self.assertEqual(state["rules"]["admin_tg_ids"], [1001])
        self.assertEqual(state["rules"]["exempt_tg_ids"], [2002])
        self.assertEqual(state["rules"]["exempt_ids"], [3003])
        self.assertEqual(state["rules"]["provider_profiles"][0]["key"], "mts")
        self.assertTrue(self.store.is_admin_tg_id(1001))
        self.assertFalse(self.store.is_admin_tg_id(2002))

    def test_provider_profiles_are_persisted_in_saved_rules(self):
        updated = self.store.update_live_rules(
            {
                "provider_profiles": [
                    {
                        "key": "rostelecom",
                        "classification": "mixed",
                        "aliases": ["rostelecom", "onlime"],
                        "mobile_markers": ["mobile", "lte"],
                        "home_markers": ["fiber", "gpon"],
                        "asns": [8359],
                    }
                ],
                "settings": {
                    "provider_mobile_marker_bonus": 20,
                    "provider_home_marker_penalty": -22,
                    "provider_conflict_review_only": True,
                },
            },
            "admin",
            1001,
        )
        self.assertEqual(updated["rules"]["provider_profiles"][0]["key"], "rostelecom")
        self.assertEqual(updated["rules"]["settings"]["provider_mobile_marker_bonus"], 20)
        with open(self.config_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["provider_profiles"][0]["key"], "rostelecom")

    def test_list_review_cases_filters_by_dates_identifiers_and_repeat_count(self):
        first_user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        second_user = {"uuid": "uuid-2", "username": "bob", "telegramId": "2002", "id": 77}

        first_bundle = DecisionBundle(
            ip="10.10.10.10",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=18,
            asn=12345,
            isp="ISP-A",
        )
        second_bundle = DecisionBundle(
            ip="10.10.10.11",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=None,
            isp="ISP-B",
        )

        first_event = self.store.record_analysis_event(first_user, first_bundle.ip, "TAG", first_bundle)
        first_case = self.store.ensure_review_case(first_user, first_bundle.ip, "TAG", first_bundle, first_event, "probable_home")
        second_event = self.store.record_analysis_event(second_user, second_bundle.ip, "TAG", second_bundle)
        second_case = self.store.ensure_review_case(second_user, second_bundle.ip, "TAG", second_bundle, second_event, "unsure")

        with self.store._connect() as conn:
            conn.execute(
                "UPDATE review_cases SET opened_at = ?, repeat_count = ? WHERE id = ?",
                ("2026-04-01T10:00:00", 3, first_case.id),
            )
            conn.execute(
                "UPDATE review_cases SET opened_at = ?, repeat_count = ? WHERE id = ?",
                ("2026-04-03T09:00:00", 1, second_case.id),
            )
            conn.commit()

        filtered = self.store.list_review_cases(
            {
                "username": "ali",
                "system_id": 42,
                "telegram_id": "1001",
                "opened_from": "2026-04-01",
                "opened_to": "2026-04-01",
                "repeat_count_min": 2,
                "repeat_count_max": 4,
            }
        )

        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["items"][0]["id"], first_case.id)
        self.assertEqual(filtered["items"][0]["system_id"], 42)
        self.assertEqual(filtered["items"][0]["opened_at"], "2026-04-01T10:00:00")

    def test_list_review_cases_sorts_by_usage_priority(self):
        first_user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        second_user = {"uuid": "uuid-2", "username": "bob", "telegramId": "2002", "id": 77}

        first_bundle = DecisionBundle(
            ip="10.10.10.10",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=18,
            asn=12345,
            isp="ISP-A",
        )
        second_bundle = DecisionBundle(
            ip="10.10.10.20",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-B",
        )

        first_event = self.store.record_analysis_event(first_user, first_bundle.ip, "TAG", first_bundle)
        first_case = self.store.ensure_review_case(first_user, first_bundle.ip, "TAG", first_bundle, first_event, "probable_home")
        second_event = self.store.record_analysis_event(second_user, second_bundle.ip, "TAG", second_bundle)
        second_case = self.store.ensure_review_case(second_user, second_bundle.ip, "TAG", second_bundle, second_event, "unsure")

        with self.store._connect() as conn:
            conn.execute(
                "UPDATE review_cases SET usage_profile_priority = ? WHERE id = ?",
                (1200, second_case.id),
            )
            conn.execute(
                "UPDATE review_cases SET usage_profile_priority = ? WHERE id = ?",
                (400, first_case.id),
            )
            conn.commit()

        listing = self.store.list_review_cases({"sort": "priority_desc"})

        self.assertEqual(listing["items"][0]["id"], second_case.id)
        self.assertEqual(listing["items"][1]["id"], first_case.id)

    def test_list_review_cases_prefers_module_name_and_falls_back_to_modules_table(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42, "module_id": "node-a", "module_name": "Node A"}
        bundle = DecisionBundle(
            ip="10.10.10.10",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=18,
            asn=12345,
            isp="ISP-A",
        )
        self.store.register_module(
            "node-a",
            "token-a",
            module_name="Readable Node",
            protocol_version="v1",
            auto_create=True,
        )
        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        summary = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "probable_home")

        with self.store._connect() as conn:
            conn.execute("UPDATE review_cases SET module_name = '' WHERE id = ?", (summary.id,))
            conn.commit()

        listing = self.store.list_review_cases({})

        self.assertEqual(listing["items"][0]["module_name"], "Readable Node")

    def test_quality_metrics_include_promoted_and_legacy_learning_state(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        bundle = DecisionBundle(
            ip="10.10.10.10",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=18,
            asn=12345,
            isp="ISP",
        )
        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        summary = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "probable_home")
        self.store.resolve_review_case(summary.id, "HOME", "admin", 1001, "confirmed")

        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO unsure_learning (pattern_type, pattern_value, decision, confidence, timestamp)
                VALUES ('asn', '12345', 'HOME', 7, '2026-04-01T10:00:00')
                """
            )
            conn.commit()

        metrics = self.store.get_quality_metrics()

        self.assertIn("learning", metrics)
        self.assertGreaterEqual(metrics["learning"]["promoted"]["active_patterns"], 1)
        self.assertEqual(metrics["learning"]["legacy"]["total_patterns"], 1)
        self.assertEqual(metrics["learning"]["legacy"]["total_confidence"], 7)
        self.assertEqual(metrics["learning"]["thresholds"]["asn_min_support"], 1)
        self.assertEqual(metrics["asn_source"]["type"], "missing")

    def test_quality_metrics_include_mixed_provider_conflict_rate(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        bundle = DecisionBundle(
            ip="10.10.10.20",
            verdict="HOME",
            confidence_band="HIGH_HOME",
            score=-18,
            asn=12345,
            isp="MTS Fiber",
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "provider_classification": "mixed",
            "service_type_hint": "home",
            "service_conflict": False,
            "review_recommended": True,
        }
        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "provider_conflict")

        metrics = self.store.get_quality_metrics()

        self.assertEqual(metrics["mixed_providers"]["open_cases"], 1)
        self.assertEqual(metrics["mixed_providers"]["conflict_cases"], 1)
        self.assertEqual(metrics["mixed_providers"]["top_open_cases"][0]["provider_key"], "mts")

    def test_review_cases_stay_separate_across_different_ips_even_with_same_telegram(self):
        self.store.register_module(
            "node-a",
            "token-a",
            module_name="Node A",
            protocol_version="v1",
            auto_create=True,
        )
        self.store.register_module(
            "node-b",
            "token-b",
            module_name="Node B",
            protocol_version="v1",
            auto_create=True,
        )
        first_user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42, "module_id": "node-a", "module_name": "Node A"}
        second_user = {"uuid": "uuid-2", "username": "alice-alt", "telegramId": "1001", "id": 77, "module_id": "node-b", "module_name": "Node B"}
        first_bundle = DecisionBundle(
            ip="10.10.10.10",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-A",
        )
        second_bundle = DecisionBundle(
            ip="10.10.10.11",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-B",
        )

        first_event = self.store.record_analysis_event(first_user, first_bundle.ip, "TAG", first_bundle)
        first_case = self.store.ensure_review_case(first_user, first_bundle.ip, "TAG", first_bundle, first_event, "unsure")
        second_event = self.store.record_analysis_event(second_user, second_bundle.ip, "TAG", second_bundle)
        second_case = self.store.ensure_review_case(second_user, second_bundle.ip, "TAG", second_bundle, second_event, "unsure")
        first_detail = self.store.get_review_case(first_case.id)
        second_detail = self.store.get_review_case(second_case.id)
        modules = {item["module_id"]: item["open_review_cases"] for item in self.store.list_modules()}

        self.assertNotEqual(first_case.id, second_case.id)
        self.assertEqual(first_detail["subject_key"], "tg:1001")
        self.assertEqual(second_detail["subject_key"], "tg:1001")
        self.assertEqual(first_detail["target_scope_type"], "subject_ip")
        self.assertEqual(second_detail["target_scope_type"], "subject_ip")
        self.assertEqual(first_detail["ip"], "10.10.10.10")
        self.assertEqual(second_detail["ip"], "10.10.10.11")
        self.assertEqual(first_detail["distinct_ip_count"], 1)
        self.assertEqual(second_detail["distinct_ip_count"], 1)
        self.assertEqual(
            {entry["ip"] for entry in first_detail["same_device_ip_history"]},
            {"10.10.10.10", "10.10.10.11"},
        )
        self.assertEqual(
            {entry["ip"] for entry in second_detail["same_device_ip_history"]},
            {"10.10.10.10", "10.10.10.11"},
        )
        self.assertEqual(first_detail["module_count"], 1)
        self.assertEqual(second_detail["module_count"], 1)
        self.assertEqual(modules["node-a"], 1)
        self.assertEqual(modules["node-b"], 1)

    def test_review_cases_stay_separate_for_different_accounts_on_same_ip_without_device_id(self):
        first_user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        second_user = {"uuid": "uuid-2", "username": "bob", "telegramId": "2002", "id": 77}
        bundle = DecisionBundle(
            ip="10.10.10.42",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-A",
        )

        first_event = self.store.record_analysis_event(first_user, bundle.ip, "TAG", bundle)
        first_case = self.store.ensure_review_case(first_user, bundle.ip, "TAG", bundle, first_event, "unsure")
        second_event = self.store.record_analysis_event(second_user, bundle.ip, "TAG", bundle)
        second_case = self.store.ensure_review_case(second_user, bundle.ip, "TAG", bundle, second_event, "unsure")

        first_detail = self.store.get_review_case(first_case.id)
        second_detail = self.store.get_review_case(second_case.id)

        self.assertNotEqual(first_case.id, second_case.id)
        self.assertEqual(first_detail["target_scope_type"], "subject_ip")
        self.assertEqual(second_detail["target_scope_type"], "subject_ip")
        self.assertNotEqual(first_detail["case_scope_key"], second_detail["case_scope_key"])
        self.assertNotEqual(first_detail["device_scope_key"], second_detail["device_scope_key"])

    def test_review_cases_merge_by_same_device_and_same_ip_scope(self):
        first_user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        second_user = {"uuid": "uuid-2", "username": "alice-alt", "telegramId": "2002", "id": 77}
        bundle = DecisionBundle(
            ip="10.10.10.42",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-A",
        )

        first_event = self.store.record_analysis_event(
            first_user,
            bundle.ip,
            "TAG",
            bundle,
            observation={"client_device_id": "dev-1", "client_device_label": "Pixel 8"},
        )
        with self.store._connect() as conn:
            conn.execute("UPDATE analysis_events SET created_at = ? WHERE id = ?", ("2026-04-01T10:00:00", first_event))
            conn.commit()
        first_case = self.store.ensure_review_case(first_user, bundle.ip, "TAG", bundle, first_event, "unsure")

        second_event = self.store.record_analysis_event(
            second_user,
            bundle.ip,
            "TAG",
            bundle,
            observation={"client_device_id": "dev-1", "client_device_label": "Pixel 8"},
        )
        with self.store._connect() as conn:
            conn.execute("UPDATE analysis_events SET created_at = ? WHERE id = ?", ("2026-04-01T10:08:00", second_event))
            conn.commit()
        second_case = self.store.ensure_review_case(second_user, bundle.ip, "TAG", bundle, second_event, "unsure")

        detail = self.store.get_review_case(second_case.id)

        self.assertEqual(first_case.id, second_case.id)
        self.assertEqual(second_case.repeat_count, 2)
        self.assertEqual(detail["target_scope_type"], "ip_device")
        self.assertEqual(detail["device_scope_key"], "device:dev-1")

    def test_list_review_cases_batches_same_device_ip_history(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        first_bundle = DecisionBundle(
            ip="10.10.10.50",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-A",
        )
        second_bundle = DecisionBundle(
            ip="10.10.10.70",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-B",
        )

        first_event = self.store.record_analysis_event(
            user,
            first_bundle.ip,
            "TAG",
            first_bundle,
            observation={"client_device_id": "dev-1", "client_device_label": "Pixel 8"},
        )
        first_case = self.store.ensure_review_case(
            user,
            first_bundle.ip,
            "TAG",
            first_bundle,
            first_event,
            "unsure",
        )
        self.store.record_analysis_event(
            user,
            "10.10.10.51",
            "TAG",
            first_bundle,
            observation={"client_device_id": "dev-1", "client_device_label": "Pixel 8"},
        )
        second_event = self.store.record_analysis_event(
            user,
            second_bundle.ip,
            "TAG",
            second_bundle,
            observation={"client_device_id": "dev-2", "client_device_label": "Pixel 9"},
        )
        second_case = self.store.ensure_review_case(
            user,
            second_bundle.ip,
            "TAG",
            second_bundle,
            second_event,
            "unsure",
        )

        with patch.object(
            self.store.review_admin,
            "_same_device_ip_history",
            side_effect=AssertionError("review listing should batch same-device history"),
        ):
            listing = self.store.list_review_cases({})

        items = {item["id"]: item for item in listing["items"]}
        self.assertEqual({first_case.id, second_case.id}, set(items))
        self.assertEqual(
            {entry["ip"] for entry in items[first_case.id]["same_device_ip_history"]},
            {"10.10.10.50", "10.10.10.51"},
        )
        self.assertEqual(len(items[first_case.id]["same_device_ip_history"]), 2)
        self.assertEqual(
            {entry["ip"] for entry in items[second_case.id]["same_device_ip_history"]},
            {"10.10.10.70"},
        )

    def test_subject_ip_cases_do_not_infer_shared_account_from_multiple_exact_devices(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        bundle = DecisionBundle(
            ip="10.10.10.80",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-A",
        )

        first_event = self.store.record_analysis_event(
            user,
            bundle.ip,
            "TAG",
            bundle,
            observation={"client_device_label": "iPhone 15"},
        )
        case = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, first_event, "unsure")
        self.store.record_analysis_event(
            user,
            "10.10.10.81",
            "TAG",
            bundle,
            observation={"client_device_id": "dev-1", "client_device_label": "iPhone 15"},
        )
        self.store.record_analysis_event(
            user,
            "10.10.10.82",
            "TAG",
            bundle,
            observation={"client_device_id": "dev-2", "client_device_label": "Pixel 8"},
        )

        detail = self.store.get_review_case(case.id)
        listing = self.store.list_review_cases({})
        listed = next(item for item in listing["items"] if item["id"] == case.id)

        self.assertEqual(detail["target_scope_type"], "subject_ip")
        self.assertFalse(detail["shared_account_suspected"])
        self.assertFalse(detail["latest_event"]["shared_account_suspected"])
        self.assertFalse(listed["shared_account_suspected"])

    def test_hwid_limit_exceeded_sets_hard_flag_and_shared_account_flag(self):
        user = {
            "uuid": "uuid-1",
            "username": "alice",
            "telegramId": "1001",
            "id": 42,
            "hwidDeviceLimit": 1,
            "hwidDevices": [
                {"hwid": "hwid-1", "deviceModel": "Pixel 8"},
                {"hwid": "hwid-2", "deviceModel": "iPhone 15"},
            ],
        }
        bundle = DecisionBundle(
            ip="10.10.10.83",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-A",
        )

        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        case = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "unsure")

        detail = self.store.get_review_case(case.id)
        listing = self.store.list_review_cases({})
        listed = next(item for item in listing["items"] if item["id"] == case.id)

        self.assertIn("sharing_hwid_limit_exceeded", detail["hard_flags"])
        self.assertIn("sharing_hwid_limit_exceeded", detail["latest_event"]["hard_flags"])
        self.assertIn("sharing_hwid_limit_exceeded", listed["hard_flags"])
        self.assertTrue(detail["shared_account_suspected"])
        self.assertTrue(detail["latest_event"]["shared_account_suspected"])
        self.assertTrue(listed["shared_account_suspected"])
        self.assertEqual(detail["hwid_device_limit"], 1)
        self.assertEqual(detail["hwid_device_count_exact"], 2)

    def test_byte_based_traffic_burst_sets_hard_flag(self):
        user = {
            "uuid": "uuid-1",
            "username": "alice",
            "telegramId": "1001",
            "id": 42,
            "usageProfileTrafficStats": {
                "series": [
                    {"timestamp": "2026-04-22T10:00:00", "node-a": 300 * 1024 * 1024},
                    {"timestamp": "2026-04-22T10:10:00", "node-a": 400 * 1024 * 1024},
                ]
            },
        }
        bundle = DecisionBundle(
            ip="10.10.10.84",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-A",
        )

        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        case = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "unsure")

        detail = self.store.get_review_case(case.id)

        self.assertIn("traffic_burst_confirmed", detail["hard_flags"])
        self.assertIn("traffic_burst", detail["usage_profile_soft_reasons"])

    def test_event_count_traffic_burst_stays_soft_only(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        bundle = DecisionBundle(
            ip="10.10.10.85",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP-A",
        )

        event_id = None
        for _index in range(5):
            event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        case = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "unsure")

        detail = self.store.get_review_case(case.id)

        self.assertIn("traffic_burst", detail["usage_profile_soft_reasons"])
        self.assertNotIn("traffic_burst_confirmed", detail["hard_flags"])

    def test_quality_metrics_use_persisted_provider_summary_without_bundle_decode(self):
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        bundle = DecisionBundle(
            ip="10.10.10.21",
            verdict="HOME",
            confidence_band="HIGH_HOME",
            score=-18,
            asn=12345,
            isp="MTS Fiber",
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "provider_classification": "mixed",
            "service_type_hint": "home",
            "service_conflict": False,
            "review_recommended": True,
        }
        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "provider_conflict")

        with self.store._connect() as conn:
            conn.execute("UPDATE analysis_events SET bundle_json = ? WHERE id = ?", ("{invalid", event_id))
            conn.commit()

        metrics = self.store.get_quality_metrics()

        self.assertEqual(metrics["mixed_providers"]["open_cases"], 1)
        self.assertEqual(metrics["mixed_providers"]["top_open_cases"][0]["provider_key"], "mts")

    def test_quality_and_health_snapshots_use_short_ttl_cache(self):
        metrics_before = self.store.get_quality_metrics()
        health_before = self.store.get_health_snapshot()

        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001", "id": 42}
        bundle = DecisionBundle(
            ip="10.10.10.30",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12345,
            isp="ISP",
        )
        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "unsure")

        metrics_cached = self.store.get_quality_metrics()
        health_cached = self.store.get_health_snapshot()
        self.store._read_cache.clear()
        metrics_refreshed = self.store.get_quality_metrics()
        health_refreshed = self.store.get_health_snapshot()

        self.assertEqual(metrics_cached["open_cases"], metrics_before["open_cases"])
        self.assertEqual(health_cached["analysis_24h"]["total"], health_before["analysis_24h"]["total"])
        self.assertEqual(metrics_refreshed["open_cases"], metrics_before["open_cases"] + 1)
        self.assertEqual(health_refreshed["analysis_24h"]["total"], health_before["analysis_24h"]["total"] + 1)

    def test_build_review_url_falls_back_to_base_config_when_live_rules_are_empty(self):
        self.assertEqual(
            self.store.build_review_url(7),
            "https://mobguard.example.com/reviews/7",
        )

    def test_overview_and_pipeline_use_stale_cache_when_fast_read_hits_locked_db(self):
        overview_before = self.store.get_overview_metrics()
        pipeline_before = self.store.get_ingest_pipeline_status()
        modules_before = self.store.list_modules(include_counters=False, fast_read=True)

        started_at = time.monotonic()
        with patch.object(self.store, "_read_snapshot_payload", side_effect=sqlite3.OperationalError("database is locked")):
            overview_cached = self.store.get_overview_metrics(fast_read=True)
            pipeline_cached = self.store.get_ingest_pipeline_status(fast_read=True)
            modules_cached = self.store.list_modules(include_counters=False, fast_read=True)
        elapsed = time.monotonic() - started_at

        self.assertLess(elapsed, 2.0)
        self.assertEqual(
            overview_cached["quality"].get("open_cases"),
            overview_before["quality"].get("open_cases"),
        )
        self.assertEqual(pipeline_cached["queue_depth"], pipeline_before["queue_depth"])
        self.assertTrue(pipeline_cached["stale"])
        self.assertTrue(overview_cached["pipeline"]["stale"])
        self.assertEqual(len(modules_cached), len(modules_before))

    def test_overview_reads_last_good_snapshot_without_live_rebuild(self):
        snapshot = self.store.get_overview_metrics()

        with patch.object(
            self.store,
            "refresh_overview_snapshot",
            side_effect=sqlite3.OperationalError("database is locked"),
        ):
            served = self.store.get_overview_metrics()

        self.assertEqual(served["quality"], snapshot["quality"])
        self.assertIn("pipeline", served)

    def test_fast_read_raises_when_snapshot_is_missing_and_db_is_locked(self):
        self.store._read_cache.clear()
        with self.store._connect() as conn:
            conn.execute("DELETE FROM read_model_snapshots WHERE snapshot_type IN (?, ?)", ("overview", "ingest_pipeline"))
            conn.commit()

        lock_conn = sqlite3.connect(self.db_path, timeout=1, check_same_thread=False)
        self.addCleanup(lock_conn.close)
        lock_conn.execute("PRAGMA busy_timeout = 1000")
        lock_conn.execute("BEGIN IMMEDIATE")
        lock_conn.execute(
            """
            INSERT INTO module_heartbeats (
                module_id, status, version, protocol_version, config_revision_applied, details_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("node-a", "online", "1.0.0", "v1", 1, json.dumps({"locked": True}), "2026-04-12T00:00:00"),
        )

        started_at = time.monotonic()
        with self.assertRaises(ReadSnapshotUnavailableError):
            self.store.get_ingest_pipeline_status(fast_read=True)
        with self.assertRaises(ReadSnapshotUnavailableError):
            self.store.get_overview_metrics(fast_read=True)
        elapsed = time.monotonic() - started_at

        lock_conn.rollback()

        self.assertLess(elapsed, 2.0)

    def test_ingest_pipeline_snapshot_refresh_is_throttled_while_dirty(self):
        self.store.mark_ingest_pipeline_snapshot_dirty()

        with patch("mobguard_platform.store.time.monotonic", side_effect=[100.0, 100.2, 100.4]):
            with patch.object(self.store, "refresh_ingest_pipeline_snapshot") as refresh_snapshot:
                first = self.store.refresh_due_ingest_pipeline_snapshot()
                second = self.store.refresh_due_ingest_pipeline_snapshot()
                third = self.store.refresh_due_ingest_pipeline_snapshot()

        refresh_snapshot.assert_called_once_with(low_priority=True)
        self.assertTrue(first["refreshed"])
        self.assertFalse(second["attempted"])
        self.assertFalse(third["attempted"])

    def test_review_payload_normalizes_numeric_uuid_to_system_id_for_legacy_rows(self):
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO analysis_events (
                    created_at, module_id, module_name, uuid, username, system_id, telegram_id, ip, tag,
                    verdict, confidence_band, score, isp, asn, punitive_eligible,
                    reasons_json, signal_flags_json, bundle_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "2026-04-12T10:00:00",
                    "node-a",
                    "Node A",
                    "215",
                    None,
                    None,
                    None,
                    "1.2.3.4",
                    "TAG",
                    "UNSURE",
                    "UNSURE",
                    0,
                    "ISP",
                    None,
                    0,
                    "[]",
                    "{}",
                    "{}",
                ),
            )
            event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO review_cases (
                    unique_key, status, review_reason, module_id, module_name, uuid, username, system_id, telegram_id,
                    ip, tag, verdict, confidence_band, score, isp, asn, punitive_eligible,
                    latest_event_id, repeat_count, reason_codes_json, opened_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy:215:1.2.3.4:TAG",
                    "OPEN",
                    "unsure",
                    "node-a",
                    "Node A",
                    "215",
                    None,
                    None,
                    None,
                    "1.2.3.4",
                    "TAG",
                    "UNSURE",
                    "UNSURE",
                    0,
                    "ISP",
                    None,
                    0,
                    event_id,
                    1,
                    "[]",
                    "2026-04-12T10:00:00",
                    "2026-04-12T10:01:00",
                ),
            )
            case_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()

        detail = self.store.get_review_case(case_id)
        listing = self.store.list_review_cases({})

        self.assertIsNone(detail["uuid"])
        self.assertEqual(detail["system_id"], 215)
        self.assertEqual(listing["items"][0]["system_id"], 215)
        self.assertIsNone(listing["items"][0]["uuid"])

    def test_bootstrap_updated_by_is_normalized_to_system(self):
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "admin_tg_ids": [1001],
                    "settings": {"threshold_mobile": 60},
                    "_meta": {"revision": 1, "updated_at": "", "updated_by": "bootstrap"},
                },
                handle,
                ensure_ascii=False,
            )
        state = self.store.get_live_rules_state()
        self.assertEqual(state["updated_by"], "system")

    def test_init_schema_migrates_legacy_tables_before_creating_system_id_indexes(self):
        legacy_db_path = os.path.join(self.temp_dir, "legacy.sqlite3")
        with sqlite3.connect(legacy_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE analysis_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    uuid TEXT,
                    username TEXT,
                    telegram_id TEXT,
                    ip TEXT NOT NULL,
                    tag TEXT,
                    verdict TEXT NOT NULL,
                    confidence_band TEXT NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    isp TEXT,
                    asn INTEGER,
                    punitive_eligible INTEGER NOT NULL DEFAULT 0,
                    reasons_json TEXT NOT NULL,
                    signal_flags_json TEXT NOT NULL,
                    bundle_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE review_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unique_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    review_reason TEXT NOT NULL,
                    uuid TEXT,
                    username TEXT,
                    telegram_id TEXT,
                    ip TEXT NOT NULL,
                    tag TEXT,
                    verdict TEXT NOT NULL,
                    confidence_band TEXT NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    isp TEXT,
                    asn INTEGER,
                    latest_event_id INTEGER NOT NULL,
                    repeat_count INTEGER NOT NULL DEFAULT 1,
                    reason_codes_json TEXT NOT NULL,
                    opened_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE live_rules (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    rules_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE admin_sessions (
                    token TEXT PRIMARY KEY,
                    telegram_id INTEGER NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE review_labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL,
                    event_id INTEGER NOT NULL,
                    pattern_type TEXT NOT NULL,
                    pattern_value TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE ip_decisions (
                    ip TEXT PRIMARY KEY,
                    status TEXT,
                    confidence TEXT,
                    details TEXT,
                    asn INTEGER,
                    expires TEXT,
                    log_json TEXT
                )
                """
            )
            conn.commit()

        legacy_store = PlatformStore(legacy_db_path, self.base_config, self.config_path)
        legacy_store.init_schema()

        with legacy_store._connect() as conn:
            analysis_columns = {row["name"] for row in conn.execute("PRAGMA table_info(analysis_events)").fetchall()}
            review_columns = {row["name"] for row in conn.execute("PRAGMA table_info(review_cases)").fetchall()}
            indexes = {
                row["name"] for row in conn.execute("PRAGMA index_list(review_cases)").fetchall()
            }

        self.assertIn("system_id", analysis_columns)
        self.assertIn("country", analysis_columns)
        self.assertIn("client_device_label", analysis_columns)
        self.assertIn("system_id", review_columns)
        self.assertIn("usage_profile_priority", review_columns)
        self.assertIn("usage_profile_summary", review_columns)
        self.assertIn("idx_review_cases_system_id", indexes)
        self.assertIn("idx_review_cases_uuid_updated", indexes)
        self.assertIn("idx_review_cases_username_updated", indexes)

    def test_health_snapshot_reflects_core_heartbeat(self):
        previous = os.environ.get("IPINFO_TOKEN")
        os.environ["IPINFO_TOKEN"] = "test-token"
        try:
            self.store.update_service_heartbeat("mobguard-core", "ok", {"shadow_mode": True})
            snapshot = self.store.get_health_snapshot()
            self.assertEqual(snapshot["status"], "ok")
            self.assertTrue(snapshot["core"]["healthy"])
            self.assertEqual(snapshot["core"]["mode"], "heartbeat")
            self.assertTrue(snapshot["ipinfo_token_present"])
        finally:
            if previous is None:
                os.environ.pop("IPINFO_TOKEN", None)
            else:
                os.environ["IPINFO_TOKEN"] = previous

    def test_health_snapshot_uses_embedded_runtime_when_heartbeat_is_missing(self):
        previous = os.environ.get("IPINFO_TOKEN")
        os.environ["IPINFO_TOKEN"] = "test-token"
        try:
            snapshot = self.store.get_health_snapshot()
            self.assertEqual(snapshot["status"], "ok")
            self.assertTrue(snapshot["core"]["healthy"])
            self.assertEqual(snapshot["core"]["mode"], "embedded")
            self.assertEqual(snapshot["core"]["status"], "embedded")
            self.assertTrue(snapshot["core"]["updated_at"])
        finally:
            if previous is None:
                os.environ.pop("IPINFO_TOKEN", None)
            else:
                os.environ["IPINFO_TOKEN"] = previous

    def test_health_snapshot_degrades_without_ipinfo_token(self):
        previous = os.environ.pop("IPINFO_TOKEN", None)
        try:
            self.store.update_service_heartbeat("mobguard-core", "ok", {"shadow_mode": True})
            snapshot = self.store.get_health_snapshot()
            self.assertEqual(snapshot["status"], "degraded")
            self.assertFalse(snapshot["ipinfo_token_present"])
        finally:
            if previous is not None:
                os.environ["IPINFO_TOKEN"] = previous


if __name__ == "__main__":
    unittest.main()
