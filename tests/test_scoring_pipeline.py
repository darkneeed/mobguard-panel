import json
import asyncio
import unittest
from pathlib import Path

from mobguard_core.scoring import ScoringContext, ScoringDependencies, evaluate_mobile_network
from mobguard_platform import review_reason_for_bundle


BASE_CONFIG = {
    "pure_mobile_asns": [51547],
    "pure_home_asns": [9049],
    "mixed_asns": [8359, 12389, 3216],
    "allowed_isp_keywords": ["mobile", "lte", "5g"],
    "home_isp_keywords": ["fiber", "ftth", "gpon"],
    "exclude_isp_keywords": ["hosting"],
    "provider_profiles": [
        {
            "key": "mts",
            "classification": "mixed",
            "aliases": ["mts", "mgts"],
            "mobile_markers": ["mobile", "lte", "5g"],
            "home_markers": ["fiber", "gpon"],
            "asns": [8359, 12389],
        },
        {
            "key": "beeline",
            "classification": "mixed",
            "aliases": ["beeline", "vimpelcom"],
            "mobile_markers": ["mobile", "lte", "5g"],
            "home_markers": ["fiber", "gpon", "home"],
            "asns": [3216],
        },
        {
            "key": "rostelecom",
            "classification": "mixed",
            "aliases": ["rostelecom", "onlime"],
            "mobile_markers": ["mobile", "lte"],
            "home_markers": ["fiber", "gpon", "onlime"],
            "asns": [8359],
        },
    ],
    "settings": {
        "pure_asn_score": 60,
        "mixed_asn_score": 45,
        "ptr_home_penalty": -20,
        "mobile_kw_bonus": 20,
        "provider_mobile_marker_bonus": 18,
        "provider_home_marker_penalty": -18,
        "ip_api_mobile_bonus": 30,
        "pure_home_asn_penalty": -100,
        "score_subnet_mobile_bonus": 40,
        "score_subnet_home_penalty": -10,
        "score_churn_high_bonus": 30,
        "score_churn_medium_bonus": 15,
        "score_stationary_penalty": -5,
        "threshold_probable_home": 30,
        "threshold_probable_mobile": 50,
        "threshold_home": 15,
        "threshold_mobile": 60,
        "auto_enforce_requires_hard_or_multi_signal": True,
        "probable_home_warning_only": True,
        "provider_conflict_review_only": True,
    },
}

RUNTIME_CONFIG = json.loads(
    (Path(__file__).resolve().parents[1] / "runtime" / "config.json").read_text(encoding="utf-8")
)


class ScoringPipelineTests(unittest.TestCase):
    def make_deps(
        self,
        *,
        manual_decision=None,
        org="AS51547 Mobile Operator",
        hostname="mobile.example",
        behavior=None,
        promoted_combo=None,
        promoted_asn=None,
        promoted_provider=None,
        promoted_provider_service=None,
        legacy_mobile=0,
        legacy_home=0,
        ip_api_mobile=None,
        datacenter_detector=None,
    ):
        behavior = behavior or {
            "logs": [],
            "total_behavior_score": 0,
            "concurrency_immunity": False,
            "churn_bonus": 0,
            "churn_rate": 0,
            "history_summary": {},
            "history_mobile_bonus": 0,
            "history_home_penalty": 0,
            "lifetime_penalty": 0,
            "lifetime_hours": 0,
            "subnet_bonus": 0,
            "subnet": None,
        }
        recorded = {"decisions": [], "stats": []}

        async def get_manual_override(_ip):
            return manual_decision

        async def get_ip_info(_ip):
            return {"org": org, "hostname": hostname}

        async def analyze_behavior(_uuid, _ip, _tag):
            return behavior

        async def get_promoted_pattern(pattern_type, pattern_value):
            if pattern_type == "combo":
                return promoted_combo
            if pattern_type == "provider":
                return promoted_provider
            if pattern_type == "provider_service":
                return promoted_provider_service
            if pattern_type == "asn":
                return promoted_asn
            return None

        async def get_legacy_confidence(_pattern_type, _pattern_value, decision):
            return legacy_mobile if decision == "MOBILE" else legacy_home

        async def check_ip_api_mobile(_ip):
            return ip_api_mobile

        async def record_decision(ip, uuid, verdict):
            recorded["decisions"].append((ip, uuid, verdict))

        def record_stats(asn, verdict, matched_kw, raw_org):
            recorded["stats"].append((asn, verdict, matched_kw, raw_org))

        deps = ScoringDependencies(
            get_manual_override=get_manual_override,
            get_ip_info=get_ip_info,
            parse_asn=lambda value: int(str(value).split()[0].replace("AS", "")) if str(value).startswith("AS") else None,
            normalize_isp_name=lambda value: value,
            is_datacenter=datacenter_detector
            or (lambda raw_org, raw_hostname: "hosting" in raw_org.lower() or "hosting" in raw_hostname.lower()),
            analyze_behavior=analyze_behavior,
            get_promoted_pattern=get_promoted_pattern,
            get_legacy_confidence=get_legacy_confidence,
            check_ip_api_mobile=check_ip_api_mobile,
            record_decision=record_decision,
            record_stats=record_stats,
        )
        return deps, recorded

    def test_manual_override_short_circuits_pipeline(self):
        deps, _ = self.make_deps(manual_decision="HOME")
        bundle = asyncio.run(
            evaluate_mobile_network(ScoringContext(ip="1.1.1.1"), BASE_CONFIG, deps)
        )
        self.assertEqual(bundle.verdict, "HOME")
        self.assertEqual(bundle.confidence_band, "HIGH_HOME")
        self.assertEqual(bundle.source, "manual_override")

    def test_pure_mobile_asn_stays_mobile(self):
        deps, recorded = self.make_deps()
        bundle = asyncio.run(
            evaluate_mobile_network(ScoringContext(ip="2.2.2.2", uuid="u1", tag="TAG"), BASE_CONFIG, deps)
        )
        self.assertEqual(bundle.verdict, "MOBILE")
        self.assertEqual(bundle.confidence_band, "HIGH_MOBILE")
        self.assertEqual(recorded["decisions"][0][2], "MOBILE")

    def test_pure_home_asn_is_hard_home(self):
        deps, _ = self.make_deps(org="AS9049 Fixed Fiber", hostname="fiber.home")
        bundle = asyncio.run(
            evaluate_mobile_network(ScoringContext(ip="3.3.3.3"), BASE_CONFIG, deps)
        )
        self.assertEqual(bundle.verdict, "HOME")
        self.assertEqual(bundle.confidence_band, "HIGH_HOME")

    def test_promoted_learning_signal_is_applied(self):
        deps, _ = self.make_deps(
            org="AS12389 Mixed Provider",
            hostname="fiber.mixed.example",
            promoted_asn={"decision": "HOME", "support": 12, "precision": 0.99},
        )
        bundle = asyncio.run(
            evaluate_mobile_network(ScoringContext(ip="4.4.4.4"), BASE_CONFIG, deps)
        )
        self.assertIn("learning_asn", bundle.reason_codes)
        self.assertEqual(bundle.verdict, "HOME")

    def test_promoted_provider_service_signal_is_applied(self):
        deps, _ = self.make_deps(
            org="AS12389 MTS",
            hostname="lte.mts.mobile",
            promoted_provider_service={"decision": "MOBILE", "support": 8, "precision": 0.97},
            ip_api_mobile=True,
        )
        bundle = asyncio.run(
            evaluate_mobile_network(ScoringContext(ip="4.4.4.5"), BASE_CONFIG, deps)
        )
        self.assertIn("learning_provider_service", bundle.reason_codes)
        self.assertEqual(bundle.verdict, "MOBILE")

    def test_score_zero_degradation_remains_unsure(self):
        deps, _ = self.make_deps(org="Unknown ISP", hostname="")
        bundle = asyncio.run(
            evaluate_mobile_network(ScoringContext(ip="5.5.5.5"), BASE_CONFIG, deps)
        )
        self.assertEqual(bundle.score, 0)
        self.assertEqual(bundle.verdict, "UNSURE")

    def test_soft_negative_score_maps_to_probable_home(self):
        deps, _ = self.make_deps(
            org="Unknown ISP",
            hostname="",
            behavior={
                "logs": ["-20 Stable same IP"],
                "total_behavior_score": -20,
                "concurrency_immunity": False,
                "churn_bonus": 0,
                "churn_rate": 0,
                "history_summary": {
                    "top_same_ip": "5.5.5.5",
                    "top_same_ip_count": 6,
                    "top_same_ip_span_hours": 30,
                    "lookback_days": 14,
                    "min_gap_minutes": 30,
                },
                "history_mobile_bonus": 0,
                "history_home_penalty": -20,
                "lifetime_penalty": 0,
                "lifetime_hours": 0,
                "subnet_bonus": 0,
                "subnet": None,
            },
        )
        bundle = asyncio.run(
            evaluate_mobile_network(ScoringContext(ip="5.5.5.6", uuid="u-home", tag="TAG"), BASE_CONFIG, deps)
        )
        self.assertEqual(bundle.verdict, "HOME")
        self.assertEqual(bundle.confidence_band, "PROBABLE_HOME")

    def test_strong_negative_score_maps_to_high_home(self):
        deps, _ = self.make_deps(
            org="Unknown ISP",
            hostname="",
            behavior={
                "logs": ["-35 Stable same IP"],
                "total_behavior_score": -35,
                "concurrency_immunity": False,
                "churn_bonus": 0,
                "churn_rate": 0,
                "history_summary": {
                    "top_same_ip": "5.5.5.5",
                    "top_same_ip_count": 8,
                    "top_same_ip_span_hours": 48,
                    "lookback_days": 14,
                    "min_gap_minutes": 30,
                },
                "history_mobile_bonus": 0,
                "history_home_penalty": -35,
                "lifetime_penalty": 0,
                "lifetime_hours": 0,
                "subnet_bonus": 0,
                "subnet": None,
            },
        )
        bundle = asyncio.run(
            evaluate_mobile_network(ScoringContext(ip="5.5.5.7", uuid="u-home", tag="TAG"), BASE_CONFIG, deps)
        )
        self.assertEqual(bundle.verdict, "HOME")
        self.assertEqual(bundle.confidence_band, "HIGH_HOME")

    def test_mixed_provider_cases_capture_extended_evidence(self):
        deps, _ = self.make_deps(org="AS8359 Rostelecom", hostname="gpon.rostelecom")
        bundle = asyncio.run(
            evaluate_mobile_network(ScoringContext(ip="6.6.6.6"), BASE_CONFIG, deps)
        )
        evidence = bundle.signal_flags["provider_evidence"]
        self.assertEqual(evidence["asn_category"], "mixed")
        self.assertEqual(evidence["provider_key"], "rostelecom")
        self.assertEqual(evidence["provider_classification"], "mixed")
        self.assertEqual(evidence["service_type_hint"], "home")
        self.assertTrue(evidence["review_recommended"])
        self.assertEqual(review_reason_for_bundle(bundle), "provider_conflict")
        self.assertEqual(bundle.verdict, "HOME")

    def test_mixed_provider_conflict_requires_review_and_blocks_punitive(self):
        deps, _ = self.make_deps(org="AS12389 MTS", hostname="lte.gpon.mts")
        bundle = asyncio.run(
            evaluate_mobile_network(ScoringContext(ip="6.6.6.7"), BASE_CONFIG, deps)
        )
        evidence = bundle.signal_flags["provider_evidence"]
        self.assertTrue(evidence["service_conflict"])
        self.assertTrue(evidence["review_recommended"])
        self.assertFalse(bundle.punitive_eligible)
        self.assertEqual(review_reason_for_bundle(bundle), "provider_conflict")

    def test_mixed_provider_needs_second_non_keyword_signal_for_automation(self):
        deps, _ = self.make_deps(
            org="AS12389 MTS",
            hostname="lte.mts.mobile",
            ip_api_mobile=True,
        )
        bundle = asyncio.run(
            evaluate_mobile_network(ScoringContext(ip="6.6.6.8"), BASE_CONFIG, deps)
        )
        evidence = bundle.signal_flags["provider_evidence"]
        self.assertEqual(bundle.verdict, "MOBILE")
        self.assertFalse(evidence["review_recommended"])
        self.assertIsNone(review_reason_for_bundle(bundle))

    def test_mixed_provider_without_markers_can_auto_mobile_with_behavior_and_learning(self):
        deps, _ = self.make_deps(
            org="AS12389 MTS",
            hostname="gw.mts.example",
            promoted_provider={"decision": "MOBILE", "support": 20, "precision": 1.0},
            behavior={
                "logs": ["+40 Historical subnet rotation"],
                "total_behavior_score": 55,
                "concurrency_immunity": False,
                "churn_bonus": 15,
                "churn_rate": 2,
                "history_summary": {
                    "top_subnet": "188.120.1",
                    "top_subnet_distinct_ips": 9,
                    "lookback_days": 14,
                    "min_gap_minutes": 30,
                },
                "history_mobile_bonus": 40,
                "history_home_penalty": 0,
                "lifetime_penalty": 0,
                "lifetime_hours": 0,
                "subnet_bonus": 0,
                "subnet": None,
            },
        )
        bundle = asyncio.run(
            evaluate_mobile_network(ScoringContext(ip="6.6.6.9", uuid="u9", tag="TAG"), BASE_CONFIG, deps)
        )
        evidence = bundle.signal_flags["provider_evidence"]
        self.assertEqual(bundle.verdict, "MOBILE")
        self.assertFalse(evidence["review_recommended"])
        self.assertIn("behavior_history_mobile", bundle.reason_codes)
        self.assertIn("learning_provider", bundle.reason_codes)
        self.assertIsNone(review_reason_for_bundle(bundle))

    def test_runtime_config_removed_noisy_keywords_do_not_create_signals(self):
        exclude_keywords = tuple(RUNTIME_CONFIG["exclude_isp_keywords"])
        deps, _ = self.make_deps(
            org="AS64500 Cloud Wire Static Dom",
            hostname="wire.static.cloud.dom.example",
            datacenter_detector=lambda raw_org, raw_hostname: any(
                kw in f"{raw_org} {raw_hostname}".lower() for kw in exclude_keywords
            ),
        )
        bundle = asyncio.run(
            evaluate_mobile_network(ScoringContext(ip="7.7.7.7"), RUNTIME_CONFIG, deps)
        )
        evidence = bundle.signal_flags["provider_evidence"]
        self.assertNotIn("datacenter", bundle.reason_codes)
        self.assertNotIn("keyword_home", bundle.reason_codes)
        self.assertEqual(evidence["home_keywords"], [])
        self.assertEqual(evidence["mobile_keywords"], [])
