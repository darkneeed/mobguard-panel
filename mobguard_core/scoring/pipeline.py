from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from mobguard_platform import DecisionBundle, derive_punitive_eligibility
from mobguard_platform.runtime import RuntimeRuleView


AsyncBehaviorAnalyzer = Callable[[str, str, str], Awaitable[dict[str, Any]]]
AsyncDecisionRecorder = Callable[[str, str, str], Awaitable[None]]
AsyncManualOverrideLookup = Callable[[str], Awaitable[Optional[str]]]
AsyncPromotedPatternLookup = Callable[[str, str], Awaitable[Optional[dict[str, Any]]]]
AsyncLegacyConfidenceLookup = Callable[[str, str, str], Awaitable[int]]
AsyncIpInfoLookup = Callable[[str], Awaitable[dict[str, Any]]]
AsyncIpApiLookup = Callable[[str], Awaitable[Optional[bool]]]
StatsRecorder = Callable[[Optional[int], str, Optional[str], str], None]
DatacenterDetector = Callable[[str, str], bool]
AsnParser = Callable[[str], Optional[int]]
IspNormalizer = Callable[[str], str]


@dataclass
class ScoringContext:
    ip: str
    uuid: Optional[str] = None
    tag: Optional[str] = None


@dataclass
class ScoringDependencies:
    get_manual_override: AsyncManualOverrideLookup
    get_ip_info: AsyncIpInfoLookup
    parse_asn: AsnParser
    normalize_isp_name: IspNormalizer
    is_datacenter: DatacenterDetector
    analyze_behavior: AsyncBehaviorAnalyzer
    get_promoted_pattern: AsyncPromotedPatternLookup
    get_legacy_confidence: AsyncLegacyConfidenceLookup
    check_ip_api_mobile: AsyncIpApiLookup
    record_decision: AsyncDecisionRecorder
    record_stats: StatsRecorder


@dataclass
class MutableScoreState:
    bundle: DecisionBundle
    log: list[str] = field(default_factory=list)
    score: int = 0
    found_home_kw: list[str] = field(default_factory=list)
    found_mobile_kw: list[str] = field(default_factory=list)
    org: str = ""
    hostname: str = ""
    isp_name: str = "Unknown ISP"
    asn: Optional[int] = None
    concurrency_immunity: bool = False


def _finalize_bundle(state: MutableScoreState, rules: RuntimeRuleView, verdict: str, confidence: str, details: str) -> DecisionBundle:
    bundle = state.bundle
    bundle.verdict = verdict
    bundle.confidence_band = confidence
    bundle.score = state.score
    bundle.isp = details
    bundle.details = details
    bundle.log = list(state.log)
    if verdict == "HOME" and rules.thresholds.auto_enforce_requires_hard_or_multi_signal:
        bundle.punitive_eligible = derive_punitive_eligibility(bundle)
    elif verdict == "HOME":
        bundle.punitive_eligible = confidence == "HIGH_HOME"
    else:
        bundle.punitive_eligible = False
    return bundle


def _provider_evidence(state: MutableScoreState, rules: RuntimeRuleView) -> dict[str, Any]:
    asn_category = "unknown"
    if state.asn in rules.detection.pure_mobile_asns:
        asn_category = "pure_mobile"
    elif state.asn in rules.detection.pure_home_asns:
        asn_category = "pure_home"
    elif state.asn in rules.detection.mixed_asns:
        asn_category = "mixed"
    return {
        "asn_category": asn_category,
        "home_keywords": list(state.found_home_kw),
        "mobile_keywords": list(state.found_mobile_kw),
        "isp_name": state.isp_name,
        "hostname": state.hostname,
    }


async def evaluate_mobile_network(
    context: ScoringContext,
    config: dict[str, Any],
    deps: ScoringDependencies,
) -> DecisionBundle:
    rules = RuntimeRuleView.from_config(config)
    state = MutableScoreState(
        bundle=DecisionBundle(
            ip=context.ip,
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            isp="Unknown ISP",
            details="Unknown ISP",
        )
    )

    state.log.append(f"[ANALYSIS] Starting analysis for IP {context.ip}")

    manual_decision = await deps.get_manual_override(context.ip)
    if manual_decision:
        state.bundle.source = "manual_override"
        state.log.append(f"[ANALYSIS] Manual override: {manual_decision}")
        direction = manual_decision if manual_decision in ("MOBILE", "HOME") else "NEUTRAL"
        state.bundle.add_reason(
            code="manual_override",
            source="manual_override",
            weight=0,
            kind="hard",
            direction=direction,
            message=f"Manual override forces {manual_decision}",
            metadata={"decision": manual_decision},
        )
        if manual_decision == "MOBILE":
            return _finalize_bundle(state, rules, "MOBILE", "HIGH_MOBILE", "Manual MOBILE")
        if manual_decision == "HOME":
            state.bundle.punitive_eligible = True
            return _finalize_bundle(state, rules, "HOME", "HIGH_HOME", "Manual HOME")
        return _finalize_bundle(state, rules, "SKIP", "SKIP", "Manual SKIP")
    state.log.append("[ANALYSIS] No manual override found")

    state.log.append(" Querying IPInfo API")
    ipinfo_data = await deps.get_ip_info(context.ip)
    state.org = ipinfo_data.get("org", "")
    state.hostname = ipinfo_data.get("hostname", "")
    state.asn = deps.parse_asn(state.org)
    state.isp_name = deps.normalize_isp_name(state.org)
    state.bundle.asn = state.asn
    state.bundle.isp = state.isp_name
    state.bundle.details = state.isp_name
    state.log.append(f" IPInfo result: ASN {state.asn}, ISP '{state.isp_name}'")
    if state.hostname:
        state.log.append(f" Hostname: {state.hostname}")

    if deps.is_datacenter(state.org, state.hostname):
        penalty = -100
        state.score += penalty
        state.log.append(" Datacenter detected -> Hard block")
        state.bundle.add_reason(
            code="datacenter",
            source="datacenter",
            weight=penalty,
            kind="hard",
            direction="HOME",
            message="Datacenter or hosting footprint detected",
            metadata={"org": state.org, "hostname": state.hostname},
        )
        state.bundle.signal_flags["provider_evidence"] = _provider_evidence(state, rules)
        deps.record_stats(state.asn, "HOME", None, state.org)
        return _finalize_bundle(state, rules, "HOME", "HIGH_HOME", f"{state.isp_name} (Datacenter)")
    state.log.append(" Not a datacenter")

    state.log.append(" ASN classification")
    if state.asn in rules.detection.pure_home_asns:
        penalty = rules.weights.pure_home_asn_penalty
        state.score += penalty
        state.log.append(f" Pure HOME ASN {state.asn} ({penalty} points)")
        state.bundle.add_reason(
            code="pure_home_asn",
            source="asn_home",
            weight=penalty,
            kind="hard",
            direction="HOME",
            message=f"Pure HOME ASN {state.asn}",
            metadata={"asn": state.asn},
        )
        state.bundle.signal_flags["provider_evidence"] = _provider_evidence(state, rules)
        deps.record_stats(state.asn, "HOME", None, state.org)
        return _finalize_bundle(state, rules, "HOME", "HIGH_HOME", f"{state.isp_name} (Pure HOME ASN)")
    if state.asn in rules.detection.pure_mobile_asns:
        bonus = rules.weights.pure_asn_score
        state.score += bonus
        state.log.append(f" Pure MOBILE ASN {state.asn} (+{bonus})")
        state.bundle.add_reason(
            code="pure_mobile_asn",
            source="asn_mobile",
            weight=bonus,
            kind="soft",
            direction="MOBILE",
            message=f"Pure MOBILE ASN {state.asn}",
            metadata={"asn": state.asn},
        )
    elif state.asn in rules.detection.mixed_asns:
        bonus = rules.weights.mixed_asn_score
        state.score += bonus
        state.log.append(f" Mixed ASN {state.asn} (+{bonus})")
        state.bundle.add_reason(
            code="mixed_asn",
            source="asn_mixed",
            weight=bonus,
            kind="soft",
            direction="MOBILE",
            message=f"Mixed ASN {state.asn}",
            metadata={"asn": state.asn},
        )
    else:
        state.log.append(f" Unknown ASN {state.asn} (no bonus)")
    state.log.append(f" Score after ASN: {state.score}")

    state.log.append(" Keyword analysis")
    searchable = f"{state.isp_name} {state.hostname}".lower()
    state.found_home_kw = [kw for kw in rules.detection.home_isp_keywords if kw in searchable]
    state.found_mobile_kw = [kw for kw in rules.detection.allowed_isp_keywords if kw in searchable]
    if state.found_home_kw:
        penalty = rules.weights.ptr_home_penalty
        state.score += penalty
        state.bundle.add_reason(
            code="keyword_home",
            source="keyword",
            weight=penalty,
            kind="soft",
            direction="HOME",
            message=f"HOME keywords found: {state.found_home_kw}",
            metadata={"keywords": state.found_home_kw},
        )
    if state.found_mobile_kw:
        bonus = rules.weights.mobile_kw_bonus
        state.score += bonus
        state.bundle.add_reason(
            code="keyword_mobile",
            source="keyword",
            weight=bonus,
            kind="soft",
            direction="MOBILE",
            message=f"MOBILE keywords found: {state.found_mobile_kw}",
            metadata={"keywords": state.found_mobile_kw},
        )
    state.bundle.signal_flags["provider_evidence"] = _provider_evidence(state, rules)
    state.log.append(f" Score after keywords: {state.score}")

    state.log.append(" Behavioral analysis")
    if context.uuid and context.tag:
        behavior = await deps.analyze_behavior(context.uuid, context.ip, context.tag)
        for item in behavior["logs"]:
            state.log.append(f" {item}")
        state.score += behavior["total_behavior_score"]
        state.concurrency_immunity = behavior["concurrency_immunity"]
        state.bundle.signal_flags["concurrency_immunity"] = state.concurrency_immunity
        if behavior["churn_bonus"] > 0:
            state.bundle.add_reason(
                code="behavior_churn",
                source="behavior_churn",
                weight=behavior["churn_bonus"],
                kind="soft",
                direction="MOBILE",
                message=f"High churn: {behavior['churn_rate']} IPs",
                metadata={"churn_rate": behavior["churn_rate"]},
            )
        if behavior["lifetime_penalty"] < 0:
            state.bundle.add_reason(
                code="behavior_lifetime",
                source="behavior_lifetime",
                weight=behavior["lifetime_penalty"],
                kind="soft",
                direction="HOME",
                message=f"Long session lifetime: {behavior['lifetime_hours']:.1f}h",
                metadata={"lifetime_hours": behavior["lifetime_hours"]},
            )
        if behavior["subnet_bonus"] != 0:
            state.bundle.add_reason(
                code="behavior_subnet_mobile" if behavior["subnet_bonus"] > 0 else "behavior_subnet_home",
                source="behavior_subnet",
                weight=behavior["subnet_bonus"],
                kind="soft",
                direction="MOBILE" if behavior["subnet_bonus"] > 0 else "HOME",
                message="Subnet has prior evidence",
                metadata={"subnet": behavior.get("subnet")},
            )
    else:
        state.log.append(" Skipped (no uuid/tag provided)")
    state.log.append(f" Score after behavioral: {state.score}")

    state.log.append(" Machine learning check")
    if state.asn is not None:
        combo_keywords = state.found_home_kw + state.found_mobile_kw
        combo_key = f"{state.asn}+{','.join(sorted(set(combo_keywords)))}" if combo_keywords else ""
        promoted_combo = await deps.get_promoted_pattern("combo", combo_key) if combo_key else None
        promoted_asn = await deps.get_promoted_pattern("asn", str(state.asn))
        if promoted_combo:
            learned_weight = min(max(int(round(promoted_combo["precision"] * 10)), 3), 8)
            direction = "MOBILE"
            if promoted_combo["decision"] == "HOME":
                learned_weight = -learned_weight
                direction = "HOME"
            state.score += learned_weight
            state.bundle.add_reason(
                code="learning_combo",
                source="learning_combo",
                weight=learned_weight,
                kind="soft",
                direction=direction,
                message=f"Promoted combo pattern {combo_key}",
                metadata={
                    "combo_key": combo_key,
                    "support": promoted_combo["support"],
                    "precision": promoted_combo["precision"],
                },
            )
        elif promoted_asn:
            learned_weight = min(max(int(round(promoted_asn["precision"] * 8)), 2), 6)
            direction = "MOBILE"
            if promoted_asn["decision"] == "HOME":
                learned_weight = -learned_weight
                direction = "HOME"
            state.score += learned_weight
            state.bundle.add_reason(
                code="learning_asn",
                source="learning_asn",
                weight=learned_weight,
                kind="soft",
                direction=direction,
                message=f"Promoted ASN pattern {state.asn}",
                metadata={
                    "asn": state.asn,
                    "support": promoted_asn["support"],
                    "precision": promoted_asn["precision"],
                },
            )
        else:
            mobile_conf = await deps.get_legacy_confidence("asn", str(state.asn), "MOBILE")
            home_conf = await deps.get_legacy_confidence("asn", str(state.asn), "HOME")
            if mobile_conf > home_conf and mobile_conf >= 3:
                bonus = min(mobile_conf, 4)
                state.score += bonus
                state.bundle.add_reason(
                    code="legacy_learning_asn",
                    source="legacy_learning_asn",
                    weight=bonus,
                    kind="soft",
                    direction="MOBILE",
                    message=f"Legacy ASN learning {state.asn}",
                    metadata={"asn": state.asn, "support": mobile_conf},
                )
            elif home_conf > mobile_conf and home_conf >= 3:
                penalty = -min(home_conf, 4)
                state.score += penalty
                state.bundle.add_reason(
                    code="legacy_learning_asn",
                    source="legacy_learning_asn",
                    weight=penalty,
                    kind="soft",
                    direction="HOME",
                    message=f"Legacy ASN learning {state.asn}",
                    metadata={"asn": state.asn, "support": home_conf},
                )
    else:
        state.log.append(" Skipped (no ASN)")
    state.log.append(f" Score after ML: {state.score}")

    state.log.append(" Fallback ip-api check")
    if (
        state.asn in rules.detection.mixed_asns
        and rules.thresholds.threshold_home < state.score < rules.thresholds.threshold_mobile
    ):
        api_mobile = await deps.check_ip_api_mobile(context.ip)
        if api_mobile is True:
            bonus = rules.weights.ip_api_mobile_bonus
            state.score += bonus
            state.bundle.add_reason(
                code="ip_api_mobile",
                source="ip_api",
                weight=bonus,
                kind="soft",
                direction="MOBILE",
                message="ip-api confirms mobile network",
                metadata={"provider": "ip-api"},
            )
    state.log.append(f" Score after fallback: {state.score}")

    state.log.append(" Computing final verdict")
    if state.concurrency_immunity and state.score < rules.thresholds.threshold_mobile:
        verdict = "UNSURE"
        confidence = "UNSURE"
        state.bundle.add_reason(
            code="cgnat_immunity",
            source="concurrency",
            weight=0,
            kind="soft",
            direction="NEUTRAL",
            message="CGNAT immunity blocks punitive HOME verdict",
        )
    elif state.score >= rules.thresholds.threshold_mobile:
        verdict = "MOBILE"
        confidence = "HIGH_MOBILE"
    elif state.score >= rules.thresholds.threshold_probable_mobile:
        verdict = "MOBILE"
        confidence = "PROBABLE_MOBILE"
    elif state.score <= rules.thresholds.threshold_home:
        verdict = "HOME"
        confidence = "HIGH_HOME"
    elif state.score <= rules.thresholds.threshold_probable_home:
        verdict = "HOME"
        confidence = "PROBABLE_HOME"
    else:
        verdict = "UNSURE"
        confidence = "UNSURE"

    finalized = _finalize_bundle(state, rules, verdict, confidence, f"{state.isp_name} (Score {state.score})")
    if context.uuid and verdict in ("MOBILE", "HOME"):
        await deps.record_decision(context.ip, context.uuid, verdict)
    deps.record_stats(state.asn, verdict, None, state.org)
    return finalized
