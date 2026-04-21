from __future__ import annotations

from .models import DecisionBundle


def _provider_review_required(bundle: DecisionBundle) -> bool:
    evidence = bundle.signal_flags.get("provider_evidence")
    return isinstance(evidence, dict) and bool(evidence.get("review_recommended"))


def _automation_guardrail_blocked(bundle: DecisionBundle) -> bool:
    guardrail = bundle.signal_flags.get("automation_guardrail")
    return isinstance(guardrail, dict) and bool(guardrail.get("blocked"))


def derive_punitive_eligibility(bundle: DecisionBundle) -> bool:
    if _provider_review_required(bundle) or _automation_guardrail_blocked(bundle):
        return False
    if bundle.verdict != "HOME":
        return False
    if bundle.confidence_band != "HIGH_HOME":
        return False
    if bundle.has_hard_home_reason:
        return True
    return len(bundle.home_sources) >= 2


def review_reason_for_bundle(bundle: DecisionBundle) -> str | None:
    if _provider_review_required(bundle):
        return "provider_conflict"
    if bundle.verdict == "UNSURE" or bundle.confidence_band == "UNSURE":
        return "unsure"
    if bundle.confidence_band == "PROBABLE_HOME":
        return "probable_home"
    if bundle.verdict == "HOME" and bundle.confidence_band == "HIGH_HOME" and not bundle.punitive_eligible:
        return "home_requires_review"
    return None


def should_warning_only(bundle: DecisionBundle) -> bool:
    return bundle.verdict == "HOME" and bundle.confidence_band == "PROBABLE_HOME"
