import unittest

from mobguard_platform.models import DecisionBundle
from mobguard_platform.policy import (
    derive_punitive_eligibility,
    review_reason_for_bundle,
    should_warning_only,
    stationary_home_auto_resolved,
)


class PolicyGuardrailTests(unittest.TestCase):
    def test_probable_home_is_warning_only(self):
        bundle = DecisionBundle(ip="1.1.1.1", verdict="HOME", confidence_band="PROBABLE_HOME", score=10)
        bundle.add_reason("keyword_home", "keyword", -20, "soft", "HOME", "home keyword")
        self.assertTrue(should_warning_only(bundle))
        self.assertFalse(derive_punitive_eligibility(bundle))

    def test_single_soft_learning_signal_is_not_punitive(self):
        bundle = DecisionBundle(ip="1.1.1.1", verdict="HOME", confidence_band="HIGH_HOME", score=8)
        bundle.add_reason("learning_asn", "learning_asn", -4, "soft", "HOME", "promoted ASN")
        self.assertFalse(derive_punitive_eligibility(bundle))

    def test_hard_home_signal_keeps_auto_enforcement(self):
        bundle = DecisionBundle(ip="1.1.1.1", verdict="HOME", confidence_band="HIGH_HOME", score=-100)
        bundle.add_reason("datacenter", "datacenter", -100, "hard", "HOME", "datacenter detected")
        self.assertTrue(derive_punitive_eligibility(bundle))

    def test_stationary_home_can_skip_manual_review(self):
        bundle = DecisionBundle(ip="1.1.1.1", verdict="HOME", confidence_band="HIGH_HOME", score=-35)
        bundle.add_reason(
            "behavior_history_home",
            "behavior",
            -25,
            "soft",
            "HOME",
            "stable same ip",
        )
        bundle.add_reason(
            "behavior_lifetime",
            "behavior",
            -10,
            "soft",
            "HOME",
            "long session",
        )
        self.assertTrue(stationary_home_auto_resolved(bundle))
        self.assertIsNone(review_reason_for_bundle(bundle))


if __name__ == "__main__":
    unittest.main()
