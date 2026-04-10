import asyncio
import unittest

from mobguard_core.scoring import ScoringContext, ScoringDependencies, evaluate_mobile_network


BASE_CONFIG = {
    "pure_mobile_asns": [51547],
    "pure_home_asns": [9049],
    "mixed_asns": [8359, 12389, 3216],
    "allowed_isp_keywords": ["mobile", "lte", "5g", "mts", "beeline"],
    "home_isp_keywords": ["fiber", "ftth", "gpon", "rostelecom"],
    "exclude_isp_keywords": ["hosting"],
    "settings": {
        "pure_asn_score": 60,
        "mixed_asn_score": 45,
        "ptr_home_penalty": -20,
        "mobile_kw_bonus": 20,
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
    },
}


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
        legacy_mobile=0,
        legacy_home=0,
        ip_api_mobile=None,
    ):
        behavior = behavior or {
            "logs": [],
            "total_behavior_score": 0,
            "concurrency_immunity": False,
            "churn_bonus": 0,
            "churn_rate": 0,
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
            is_datacenter=lambda raw_org, raw_hostname: "hosting" in raw_org.lower() or "hosting" in raw_hostname.lower(),
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

    def test_score_zero_degradation_remains_unsure(self):
        deps, _ = self.make_deps(org="Unknown ISP", hostname="")
        bundle = asyncio.run(
            evaluate_mobile_network(ScoringContext(ip="5.5.5.5"), BASE_CONFIG, deps)
        )
        self.assertEqual(bundle.score, 0)
        self.assertEqual(bundle.verdict, "HOME")

    def test_ambiguity_metadata_is_collected_for_mixed_providers(self):
        cases = [
            ("AS8359 Rostelecom", "gpon.rostelecom", "HOME"),
            ("AS12389 MTS", "lte.mts.mobile", "MOBILE"),
            ("AS3216 Beeline", "home-gpon.beeline", "UNSURE"),
        ]
        for org, hostname, expected in cases:
            with self.subTest(org=org, hostname=hostname):
                deps, _ = self.make_deps(org=org, hostname=hostname)
                bundle = asyncio.run(
                    evaluate_mobile_network(ScoringContext(ip="6.6.6.6"), BASE_CONFIG, deps)
                )
                evidence = bundle.signal_flags["provider_evidence"]
                self.assertEqual(evidence["asn_category"], "mixed")
                self.assertTrue(evidence["home_keywords"] or evidence["mobile_keywords"])
                self.assertEqual(bundle.verdict, expected)
