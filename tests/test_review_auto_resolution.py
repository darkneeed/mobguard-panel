from __future__ import annotations

from datetime import datetime
import unittest

from api.services.review_auto_resolution import match_review_auto_resolution
from mobguard_platform import DecisionBundle


class ReviewAutoResolutionTests(unittest.TestCase):
    def test_stationary_threshold_resolves_probable_home_to_home(self):
        bundle = DecisionBundle(
            ip="10.10.10.20",
            verdict="PROBABLE_HOME",
            confidence_band="PROBABLE_HOME",
            score=-30,
            isp="Rostelecom",
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "rostelecom",
            "review_recommended": True,
        }

        match = match_review_auto_resolution(
            opened_at="2026-05-05T10:00:00",
            review_reason="probable_home",
            provider_evidence=bundle.signal_flags["provider_evidence"],
            reason_codes=bundle.reason_codes,
            reasons=bundle.reasons,
            ongoing_duration_seconds=13 * 3600,
            stationary_threshold_hours=12,
            now=datetime.fromisoformat("2026-05-06T00:00:00"),
        )

        self.assertIsNotNone(match)
        self.assertEqual(match.rule_id, "home_stationary_threshold")
        self.assertEqual(match.resolution, "HOME")
        self.assertEqual(match.audit_payload.get("stationary_threshold_hours"), 12.0)
        self.assertEqual(match.audit_payload.get("effective_activity_hours"), 13.0)

    def test_stationary_threshold_does_not_match_below_threshold(self):
        bundle = DecisionBundle(
            ip="10.10.10.21",
            verdict="PROBABLE_HOME",
            confidence_band="PROBABLE_HOME",
            score=-20,
            isp="Rostelecom",
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "rostelecom",
            "review_recommended": True,
        }

        match = match_review_auto_resolution(
            opened_at="2026-05-05T10:00:00",
            review_reason="probable_home",
            provider_evidence=bundle.signal_flags["provider_evidence"],
            reason_codes=bundle.reason_codes,
            reasons=bundle.reasons,
            ongoing_duration_seconds=11 * 3600,
            stationary_threshold_hours=12,
            now=datetime.fromisoformat("2026-05-05T22:00:00"),
        )

        self.assertIsNone(match)

    def test_short_provider_conflict_matches_mobile_rule(self):
        bundle = DecisionBundle(
            ip="10.10.10.10",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=15,
            isp="MTS",
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "review_recommended": True,
        }

        match = match_review_auto_resolution(
            opened_at="2026-05-05T10:00:00",
            review_reason="provider_conflict",
            provider_evidence=bundle.signal_flags["provider_evidence"],
            reason_codes=bundle.reason_codes,
            reasons=bundle.reasons,
            ongoing_duration_seconds=11 * 3600,
            now=datetime.fromisoformat("2026-05-05T15:59:59"),
        )

        self.assertIsNotNone(match)
        self.assertEqual(match.rule_id, "mobile_short_provider_conflict")
        self.assertEqual(match.resolution, "MOBILE")
        self.assertEqual(match.support, 114)

    def test_mts_pppoe_keyword_matches_mobile_exception_rule(self):
        bundle = DecisionBundle(
            ip="10.10.10.11",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=-14,
            isp="MTS",
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "review_recommended": True,
        }
        bundle.add_reason(
            "keyword_home",
            "generic_keyword",
            -20,
            "soft",
            "HOME",
            "HOME keywords found",
            {"keywords": ["pppoe"]},
        )

        match = match_review_auto_resolution(
            opened_at="2026-05-05T10:00:00",
            review_reason="unsure",
            provider_evidence=bundle.signal_flags["provider_evidence"],
            reason_codes=bundle.reason_codes,
            reasons=bundle.reasons,
            ongoing_duration_seconds=72 * 3600,
            now=datetime.fromisoformat("2026-05-06T10:00:00"),
        )

        self.assertIsNotNone(match)
        self.assertEqual(match.rule_id, "mobile_mts_pppoe_exception")
        self.assertEqual(match.support, 86)

    def test_provider_conflict_keyword_mobile_matches_rule(self):
        bundle = DecisionBundle(
            ip="10.10.10.12",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=20,
            isp="Beeline",
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "beeline",
            "review_recommended": True,
        }
        bundle.add_reason(
            "keyword_mobile",
            "generic_keyword",
            20,
            "soft",
            "MOBILE",
            "MOBILE keywords found",
            {"keywords": ["gprs"]},
        )

        match = match_review_auto_resolution(
            opened_at="2026-05-05T10:00:00",
            review_reason="provider_conflict",
            provider_evidence=bundle.signal_flags["provider_evidence"],
            reason_codes=bundle.reason_codes,
            reasons=bundle.reasons,
            ongoing_duration_seconds=18 * 3600,
            now=datetime.fromisoformat("2026-05-06T12:00:00"),
        )

        self.assertIsNotNone(match)
        self.assertEqual(match.rule_id, "mobile_provider_conflict_keyword")
        self.assertEqual(match.support, 25)

    def test_behavior_history_mobile_alone_does_not_match(self):
        bundle = DecisionBundle(
            ip="10.10.10.13",
            verdict="MOBILE",
            confidence_band="HIGH_MOBILE",
            score=55,
            isp="MTS",
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "review_recommended": True,
        }
        bundle.add_reason(
            "behavior_history_mobile",
            "behavior",
            40,
            "soft",
            "MOBILE",
            "Historical subnet rotation",
            {"subnet": "188.120.1"},
        )

        match = match_review_auto_resolution(
            opened_at="2026-05-05T10:00:00",
            review_reason="provider_conflict",
            provider_evidence=bundle.signal_flags["provider_evidence"],
            reason_codes=bundle.reason_codes,
            reasons=bundle.reasons,
            ongoing_duration_seconds=18 * 3600,
            now=datetime.fromisoformat("2026-05-06T12:30:00"),
        )

        self.assertIsNone(match)

    def test_unknown_provider_without_signals_does_not_match(self):
        match = match_review_auto_resolution(
            opened_at="2026-05-05T10:00:00",
            review_reason="unsure",
            provider_evidence={},
            reason_codes=[],
            reasons=[],
            ongoing_duration_seconds=72 * 3600,
            now=datetime.fromisoformat("2026-05-06T12:30:00"),
        )

        self.assertIsNone(match)

    def test_case_older_than_96_hours_does_not_auto_resolve(self):
        # Even if a rule matches (like mobile_short_provider_conflict), it should return None if case age > 96h
        bundle = DecisionBundle(
            ip="10.10.10.10",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=15,
            isp="MTS",
        )
        bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "review_recommended": True,
        }

        # Case age = 97 hours (more than 96 hours)
        match = match_review_auto_resolution(
            opened_at="2026-05-01T10:00:00",
            review_reason="provider_conflict",
            provider_evidence=bundle.signal_flags["provider_evidence"],
            reason_codes=bundle.reason_codes,
            reasons=bundle.reasons,
            ongoing_duration_seconds=11 * 3600,
            now=datetime.fromisoformat("2026-05-05T11:00:00"),
        )

        self.assertIsNone(match)


if __name__ == "__main__":
    unittest.main()
