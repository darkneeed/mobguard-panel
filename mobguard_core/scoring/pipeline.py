from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from mobguard_platform import DecisionBundle, derive_punitive_eligibility
from mobguard_platform.runtime import ProviderProfile, RuntimeRuleView


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
    matched_provider: Optional[ProviderProfile] = None
    matched_provider_aliases: list[str] = field(default_factory=list)
    found_provider_mobile_markers: list[str] = field(default_factory=list)
    found_provider_home_markers: list[str] = field(default_factory=list)
    provider_service_hint: str = "unknown"
    provider_service_conflict: bool = False
    provider_review_recommended: bool = False


@dataclass(frozen=True)
class DecisionOutcome:
    verdict: str
    confidence: str
    automation_blocked: bool = False
    automation_block_reason: str = ""


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
        "provider_key": state.matched_provider.key if state.matched_provider else None,
        "provider_classification": state.matched_provider.classification if state.matched_provider else "unknown",
        "service_type_hint": state.provider_service_hint,
        "service_conflict": state.provider_service_conflict,
        "review_recommended": state.provider_review_recommended,
        "matched_aliases": list(state.matched_provider_aliases),
        "provider_mobile_markers": list(state.found_provider_mobile_markers),
        "provider_home_markers": list(state.found_provider_home_markers),
    }


def _refresh_provider_evidence(state: MutableScoreState, rules: RuntimeRuleView) -> None:
    state.bundle.signal_flags["provider_evidence"] = _provider_evidence(state, rules)


def _match_provider_profile(state: MutableScoreState, rules: RuntimeRuleView, searchable: str) -> tuple[Optional[ProviderProfile], list[str]]:
    best_profile: Optional[ProviderProfile] = None
    best_aliases: list[str] = []
    best_score = 0
    for profile in rules.detection.provider_profiles:
        alias_hits = [alias for alias in profile.aliases if alias and alias in searchable]
        asn_hit = state.asn is not None and state.asn in profile.asns
        if not alias_hits and not asn_hit:
            continue
        score = (3 if asn_hit else 0) + len(alias_hits)
        if score > best_score:
            best_profile = profile
            best_aliases = alias_hits
            best_score = score
    return best_profile, best_aliases


def _provider_metadata(state: MutableScoreState) -> dict[str, Any]:
    return {
        "provider_key": state.matched_provider.key if state.matched_provider else "",
        "provider_classification": state.matched_provider.classification if state.matched_provider else "unknown",
        "matched_aliases": list(state.matched_provider_aliases),
        "mobile_markers": list(state.found_provider_mobile_markers),
        "home_markers": list(state.found_provider_home_markers),
        "service_type_hint": state.provider_service_hint,
    }


def _apply_provider_profile_signal(state: MutableScoreState, rules: RuntimeRuleView, searchable: str) -> None:
    profile, alias_hits = _match_provider_profile(state, rules, searchable)
    if not profile:
        _refresh_provider_evidence(state, rules)
        return

    state.matched_provider = profile
    state.matched_provider_aliases = alias_hits
    state.found_provider_mobile_markers = [
        marker for marker in profile.mobile_markers if marker and marker in searchable
    ]
    state.found_provider_home_markers = [
        marker for marker in profile.home_markers if marker and marker in searchable
    ]
    state.provider_service_conflict = bool(
        state.found_provider_mobile_markers and state.found_provider_home_markers
    )
    if state.provider_service_conflict:
        state.provider_service_hint = "conflict"
        state.bundle.add_reason(
            code="provider_conflict",
            source="provider_profile",
            weight=0,
            kind="soft",
            direction="NEUTRAL",
            message=f"Mixed provider {profile.key} exposes both HOME and MOBILE service markers",
            metadata=_provider_metadata(state),
        )
    elif state.found_provider_mobile_markers:
        bonus = rules.weights.provider_mobile_marker_bonus
        state.provider_service_hint = "mobile"
        state.score += bonus
        state.bundle.add_reason(
            code="provider_mobile_marker",
            source="provider_profile",
            weight=bonus,
            kind="soft",
            direction="MOBILE",
            message=f"Provider {profile.key} matched MOBILE service markers",
            metadata=_provider_metadata(state),
        )
    elif state.found_provider_home_markers:
        penalty = rules.weights.provider_home_marker_penalty
        state.provider_service_hint = "home"
        state.score += penalty
        state.bundle.add_reason(
            code="provider_home_marker",
            source="provider_profile",
            weight=penalty,
            kind="soft",
            direction="HOME",
            message=f"Provider {profile.key} matched HOME service markers",
            metadata=_provider_metadata(state),
        )
    else:
        state.provider_service_hint = "unknown"
        state.bundle.add_reason(
            code="provider_marker_missing",
            source="provider_profile",
            weight=0,
            kind="soft",
            direction="NEUTRAL",
            message=f"Provider {profile.key} matched without service markers",
            metadata=_provider_metadata(state),
        )
    _refresh_provider_evidence(state, rules)


def _apply_promoted_learning_reason(
    state: MutableScoreState,
    *,
    code: str,
    pattern_type: str,
    pattern_value: str,
    pattern: dict[str, Any],
    scale: int,
    min_weight: int,
    max_weight: int,
) -> None:
    learned_weight = min(max(int(round(float(pattern["precision"]) * scale)), min_weight), max_weight)
    direction = "MOBILE"
    if pattern["decision"] == "HOME":
        learned_weight = -learned_weight
        direction = "HOME"
    state.score += learned_weight
    state.bundle.add_reason(
        code=code,
        source="learning",
        weight=learned_weight,
        kind="soft",
        direction=direction,
        message=f"Promoted {pattern_type} pattern {pattern_value}",
        metadata={
            "pattern_type": pattern_type,
            "pattern_value": pattern_value,
            "support": pattern["support"],
            "precision": pattern["precision"],
        },
    )


def _apply_provider_guardrail(
    state: MutableScoreState,
    rules: RuntimeRuleView,
    provisional_verdict: str,
) -> DecisionOutcome:
    state.provider_review_recommended = False
    profile = state.matched_provider
    if not profile or profile.classification != "mixed" or not rules.thresholds.provider_conflict_review_only:
        state.bundle.signal_flags["automation_guardrail"] = {"blocked": False, "reason": ""}
        _refresh_provider_evidence(state, rules)
        return DecisionOutcome(provisional_verdict, "")

    if state.provider_service_conflict:
        state.provider_review_recommended = True
    elif state.provider_service_hint == "unknown":
        mobile_sources = state.bundle.sources_for_direction("MOBILE") - {
            "provider_profile",
            "generic_keyword",
        }
        state.provider_review_recommended = not (
            provisional_verdict == "MOBILE"
            and "behavior" in mobile_sources
            and len(mobile_sources) >= 2
        )
    elif provisional_verdict in {"HOME", "MOBILE"} and state.provider_service_hint != provisional_verdict.lower():
        state.provider_review_recommended = True
    elif state.provider_service_hint in {"home", "mobile"}:
        supporting_sources = state.bundle.sources_for_direction(state.provider_service_hint.upper()) - {
            "provider_profile",
            "generic_keyword",
        }
        state.provider_review_recommended = len(supporting_sources) == 0

    if state.provider_review_recommended:
        state.bundle.add_reason(
            code="provider_review_guardrail",
            source="provider_profile",
            weight=0,
            kind="soft",
            direction="NEUTRAL",
            message=f"Mixed provider {profile.key} requires manual review before automation",
            metadata=_provider_metadata(state),
        )
    state.bundle.signal_flags["automation_guardrail"] = {
        "blocked": state.provider_review_recommended,
        "reason": "provider_review" if state.provider_review_recommended else "",
    }
    _refresh_provider_evidence(state, rules)
    return DecisionOutcome(
        provisional_verdict,
        "",
        automation_blocked=state.provider_review_recommended,
        automation_block_reason="provider_review" if state.provider_review_recommended else "",
    )


def _derive_score_outcome(state: MutableScoreState, rules: RuntimeRuleView) -> DecisionOutcome:
    if state.concurrency_immunity and state.score < rules.thresholds.threshold_mobile:
        state.bundle.add_reason(
            code="cgnat_immunity",
            source="concurrency",
            weight=0,
            kind="soft",
            direction="NEUTRAL",
            message="CGNAT immunity blocks punitive HOME verdict",
        )
        return DecisionOutcome("UNSURE", "UNSURE")

    if state.score >= rules.thresholds.threshold_mobile:
        return DecisionOutcome("MOBILE", "HIGH_MOBILE")
    if state.score >= rules.thresholds.threshold_probable_mobile:
        return DecisionOutcome("MOBILE", "PROBABLE_MOBILE")
    if state.score <= -rules.thresholds.threshold_probable_home:
        return DecisionOutcome("HOME", "HIGH_HOME")
    if state.score <= -rules.thresholds.threshold_home:
        return DecisionOutcome("HOME", "PROBABLE_HOME")
    return DecisionOutcome("UNSURE", "UNSURE")


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

    searchable = f"{state.isp_name} {state.hostname}".lower()
    _apply_provider_profile_signal(state, rules, searchable)
    if state.matched_provider:
        state.log.append(
            f" Provider profile: {state.matched_provider.key} ({state.matched_provider.classification}, {state.provider_service_hint})"
        )

    if deps.is_datacenter(state.org, state.hostname):
        penalty = -100
        state.score += penalty
        state.log.append(" Datacenter detected -> Hard block")
        state.bundle.add_reason(
            code="datacenter",
            source="generic_keyword",
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
            source="asn",
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
            source="asn",
            weight=bonus,
            kind="soft",
            direction="MOBILE",
            message=f"Pure MOBILE ASN {state.asn}",
            metadata={"asn": state.asn},
        )
    elif state.asn in rules.detection.mixed_asns:
        if state.matched_provider and state.matched_provider.classification == "mixed":
            state.log.append(f" Mixed ASN {state.asn} guarded by provider profile")
            state.bundle.add_reason(
                code="mixed_asn_guarded",
                source="asn",
                weight=0,
                kind="soft",
                direction="NEUTRAL",
                message=f"Mixed ASN {state.asn} recorded without score because provider profile is mixed",
                metadata={"asn": state.asn},
            )
        else:
            bonus = rules.weights.mixed_asn_score
            state.score += bonus
            state.log.append(f" Mixed ASN {state.asn} (+{bonus})")
            state.bundle.add_reason(
                code="mixed_asn",
                source="asn",
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
    state.found_home_kw = [kw for kw in rules.detection.home_isp_keywords if kw in searchable]
    state.found_mobile_kw = [kw for kw in rules.detection.allowed_isp_keywords if kw in searchable]
    if state.found_home_kw:
        penalty = rules.weights.ptr_home_penalty
        state.score += penalty
        state.bundle.add_reason(
            code="keyword_home",
            source="generic_keyword",
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
            source="generic_keyword",
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
                source="behavior",
                weight=behavior["churn_bonus"],
                kind="soft",
                direction="MOBILE",
                message=f"High churn: {behavior['churn_rate']} IPs",
                metadata={"churn_rate": behavior["churn_rate"]},
            )
        if int(behavior.get("history_mobile_bonus") or 0) > 0:
            history_summary = behavior.get("history_summary", {})
            state.bundle.add_reason(
                code="behavior_history_mobile",
                source="behavior",
                weight=int(behavior.get("history_mobile_bonus") or 0),
                kind="soft",
                direction="MOBILE",
                message="Historical subnet rotation",
                metadata={
                    "subnet": history_summary.get("top_subnet"),
                    "distinct_ips": history_summary.get("top_subnet_distinct_ips"),
                    "lookback_days": history_summary.get("lookback_days"),
                    "min_gap_minutes": history_summary.get("min_gap_minutes"),
                },
            )
        if int(behavior.get("history_home_penalty") or 0) < 0:
            history_summary = behavior.get("history_summary", {})
            state.bundle.add_reason(
                code="behavior_history_home",
                source="behavior",
                weight=int(behavior.get("history_home_penalty") or 0),
                kind="soft",
                direction="HOME",
                message="Stable same IP over time",
                metadata={
                    "ip": history_summary.get("top_same_ip"),
                    "sample_count": history_summary.get("top_same_ip_count"),
                    "span_hours": history_summary.get("top_same_ip_span_hours"),
                    "lookback_days": history_summary.get("lookback_days"),
                    "min_gap_minutes": history_summary.get("min_gap_minutes"),
                },
            )
        if behavior["lifetime_penalty"] < 0:
            state.bundle.add_reason(
                code="behavior_lifetime",
                source="behavior",
                weight=behavior["lifetime_penalty"],
                kind="soft",
                direction="HOME",
                message=f"Long session lifetime: {behavior['lifetime_hours']:.1f}h",
                metadata={"lifetime_hours": behavior["lifetime_hours"]},
            )
        if behavior["subnet_bonus"] != 0:
            state.bundle.add_reason(
                code="behavior_subnet_mobile" if behavior["subnet_bonus"] > 0 else "behavior_subnet_home",
                source="behavior",
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
        provider_key = state.matched_provider.key if state.matched_provider else ""
        provider_service_key = (
            f"{provider_key}:{state.provider_service_hint}"
            if provider_key and state.provider_service_hint in {"home", "mobile", "conflict"}
            else ""
        )
        promoted_combo = await deps.get_promoted_pattern("combo", combo_key) if combo_key else None
        promoted_provider_service = (
            await deps.get_promoted_pattern("provider_service", provider_service_key)
            if provider_service_key
            else None
        )
        promoted_provider = await deps.get_promoted_pattern("provider", provider_key) if provider_key else None
        promoted_asn = await deps.get_promoted_pattern("asn", str(state.asn))
        if promoted_combo:
            _apply_promoted_learning_reason(
                state,
                code="learning_combo",
                pattern_type="combo",
                pattern_value=combo_key,
                pattern=promoted_combo,
                scale=10,
                min_weight=3,
                max_weight=8,
            )
        elif promoted_provider_service:
            _apply_promoted_learning_reason(
                state,
                code="learning_provider_service",
                pattern_type="provider_service",
                pattern_value=provider_service_key,
                pattern=promoted_provider_service,
                scale=9,
                min_weight=3,
                max_weight=7,
            )
        elif promoted_provider:
            _apply_promoted_learning_reason(
                state,
                code="learning_provider",
                pattern_type="provider",
                pattern_value=provider_key,
                pattern=promoted_provider,
                scale=8,
                min_weight=2,
                max_weight=6,
            )
        elif promoted_asn:
            _apply_promoted_learning_reason(
                state,
                code="learning_asn",
                pattern_type="asn",
                pattern_value=str(state.asn),
                pattern=promoted_asn,
                scale=8,
                min_weight=2,
                max_weight=6,
            )
        else:
            mobile_conf = await deps.get_legacy_confidence("asn", str(state.asn), "MOBILE")
            home_conf = await deps.get_legacy_confidence("asn", str(state.asn), "HOME")
            if mobile_conf > home_conf and mobile_conf >= 3:
                bonus = min(mobile_conf, 4)
                state.score += bonus
                state.bundle.add_reason(
                    code="legacy_learning_asn",
                    source="learning",
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
                    source="learning",
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
                source="fallback",
                weight=bonus,
                kind="soft",
                direction="MOBILE",
                message="ip-api confirms mobile network",
                metadata={"provider": "ip-api"},
            )
    state.log.append(f" Score after fallback: {state.score}")

    state.log.append(" Computing final verdict")
    score_outcome = _derive_score_outcome(state, rules)
    state.log.append(
        f" Score outcome: verdict={score_outcome.verdict} confidence={score_outcome.confidence} score={state.score}"
    )
    provider_outcome = _apply_provider_guardrail(state, rules, score_outcome.verdict)
    if provider_outcome.automation_blocked:
        state.log.append(
            f" Provider guardrail: automation blocked ({provider_outcome.automation_block_reason})"
        )
    else:
        state.log.append(" Provider guardrail: no block")

    finalized = _finalize_bundle(
        state,
        rules,
        score_outcome.verdict,
        score_outcome.confidence,
        f"{state.isp_name} (Score {state.score})",
    )
    if context.uuid and score_outcome.verdict in ("MOBILE", "HOME"):
        await deps.record_decision(context.ip, context.uuid, score_outcome.verdict)
    deps.record_stats(state.asn, score_outcome.verdict, None, state.org)
    return finalized
