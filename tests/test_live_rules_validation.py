import unittest

from mobguard_platform.store import validate_live_rules_patch


class LiveRulesValidationTests(unittest.TestCase):
    def test_valid_patch_normalizes_lists(self):
        payload = validate_live_rules_patch(
            {
                "mixed_asns": ["123", 456],
                "allowed_isp_keywords": ["mobile", "lte"],
                "settings": {"threshold_mobile": 70, "probable_home_warning_only": True},
            }
        )
        self.assertEqual(payload["mixed_asns"], [123, 456])
        self.assertEqual(payload["allowed_isp_keywords"], ["mobile", "lte"])
        self.assertTrue(payload["settings"]["probable_home_warning_only"])

    def test_legacy_mobile_threshold_alias_is_normalized(self):
        payload = validate_live_rules_patch(
            {
                "exempt_ids": ["42", 84],
                "exempt_tg_ids": ["1001"],
                "settings": {"mobile_score_threshold": 70},
            }
        )
        self.assertEqual(payload["exempt_ids"], [42, 84])
        self.assertEqual(payload["exempt_tg_ids"], [1001])
        self.assertEqual(payload["settings"]["threshold_mobile"], 70)
        self.assertNotIn("mobile_score_threshold", payload["settings"])

    def test_canonical_threshold_wins_over_legacy_alias(self):
        payload = validate_live_rules_patch(
            {"settings": {"threshold_mobile": 65, "mobile_score_threshold": 70}}
        )
        self.assertEqual(payload["settings"]["threshold_mobile"], 65)

    def test_invalid_setting_raises(self):
        with self.assertRaises(ValueError):
            validate_live_rules_patch({"settings": {"threshold_mobile": "high"}})

    def test_provider_profiles_are_normalized(self):
        payload = validate_live_rules_patch(
            {
                "provider_profiles": [
                    {
                        "key": "MTS",
                        "classification": "mixed",
                        "aliases": ["MTS", "mgts"],
                        "mobile_markers": ["lte", "mobile"],
                        "home_markers": ["gpon", "fiber"],
                        "asns": ["8359", 12389],
                    }
                ]
            }
        )
        self.assertEqual(
            payload["provider_profiles"],
            [
                {
                    "key": "mts",
                    "classification": "mixed",
                    "aliases": ["mts", "mgts"],
                    "mobile_markers": ["lte", "mobile"],
                    "home_markers": ["gpon", "fiber"],
                    "asns": [8359, 12389],
                }
            ],
        )

    def test_history_settings_are_accepted(self):
        payload = validate_live_rules_patch(
            {
                "settings": {
                    "history_lookback_days": 14,
                    "history_min_gap_minutes": 30,
                    "history_mobile_same_subnet_min_distinct_ips": 8,
                    "history_mobile_bonus": 40,
                    "history_home_same_ip_min_records": 5,
                    "history_home_same_ip_min_span_hours": 24,
                    "history_home_penalty": -25,
                }
            }
        )
        self.assertEqual(payload["settings"]["history_lookback_days"], 14)
        self.assertEqual(payload["settings"]["history_mobile_bonus"], 40)
        self.assertEqual(payload["settings"]["history_home_penalty"], -25)

    def test_retention_settings_are_accepted(self):
        payload = validate_live_rules_patch(
            {
                "settings": {
                    "db_cleanup_interval_minutes": 30,
                    "module_heartbeats_retention_days": 14,
                    "ingested_raw_events_retention_days": 30,
                    "ip_history_retention_days": 30,
                    "orphan_analysis_events_retention_days": 30,
                    "resolved_review_retention_days": 90,
                }
            }
        )
        self.assertEqual(payload["settings"]["db_cleanup_interval_minutes"], 30)
        self.assertEqual(payload["settings"]["module_heartbeats_retention_days"], 14)
        self.assertEqual(payload["settings"]["resolved_review_retention_days"], 90)


if __name__ == "__main__":
    unittest.main()
