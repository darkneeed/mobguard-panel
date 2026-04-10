from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DetectionRules:
    pure_mobile_asns: tuple[int, ...]
    pure_home_asns: tuple[int, ...]
    mixed_asns: tuple[int, ...]
    allowed_isp_keywords: tuple[str, ...]
    home_isp_keywords: tuple[str, ...]
    exclude_isp_keywords: tuple[str, ...]

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "DetectionRules":
        return cls(
            pure_mobile_asns=tuple(int(item) for item in config.get("pure_mobile_asns", [])),
            pure_home_asns=tuple(int(item) for item in config.get("pure_home_asns", [])),
            mixed_asns=tuple(int(item) for item in config.get("mixed_asns", [])),
            allowed_isp_keywords=tuple(str(item).lower() for item in config.get("allowed_isp_keywords", [])),
            home_isp_keywords=tuple(str(item).lower() for item in config.get("home_isp_keywords", [])),
            exclude_isp_keywords=tuple(str(item).lower() for item in config.get("exclude_isp_keywords", [])),
        )


@dataclass(frozen=True)
class ScoreWeights:
    pure_asn_score: int
    mixed_asn_score: int
    ptr_home_penalty: int
    mobile_kw_bonus: int
    ip_api_mobile_bonus: int
    pure_home_asn_penalty: int
    score_subnet_mobile_bonus: int
    score_subnet_home_penalty: int
    score_churn_high_bonus: int
    score_churn_medium_bonus: int
    score_stationary_penalty: int

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ScoreWeights":
        settings = config.get("settings", {})
        return cls(
            pure_asn_score=int(settings.get("pure_asn_score", 60)),
            mixed_asn_score=int(settings.get("mixed_asn_score", 45)),
            ptr_home_penalty=int(settings.get("ptr_home_penalty", -20)),
            mobile_kw_bonus=int(settings.get("mobile_kw_bonus", 20)),
            ip_api_mobile_bonus=int(settings.get("ip_api_mobile_bonus", 30)),
            pure_home_asn_penalty=int(settings.get("pure_home_asn_penalty", -100)),
            score_subnet_mobile_bonus=int(settings.get("score_subnet_mobile_bonus", 40)),
            score_subnet_home_penalty=int(settings.get("score_subnet_home_penalty", -10)),
            score_churn_high_bonus=int(settings.get("score_churn_high_bonus", 30)),
            score_churn_medium_bonus=int(settings.get("score_churn_medium_bonus", 15)),
            score_stationary_penalty=int(settings.get("score_stationary_penalty", -5)),
        )


@dataclass(frozen=True)
class Thresholds:
    threshold_probable_home: int
    threshold_probable_mobile: int
    threshold_home: int
    threshold_mobile: int
    auto_enforce_requires_hard_or_multi_signal: bool
    probable_home_warning_only: bool

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "Thresholds":
        settings = config.get("settings", {})
        return cls(
            threshold_probable_home=int(settings.get("threshold_probable_home", 30)),
            threshold_probable_mobile=int(settings.get("threshold_probable_mobile", 50)),
            threshold_home=int(settings.get("threshold_home", 15)),
            threshold_mobile=int(settings.get("threshold_mobile", 60)),
            auto_enforce_requires_hard_or_multi_signal=bool(
                settings.get("auto_enforce_requires_hard_or_multi_signal", True)
            ),
            probable_home_warning_only=bool(settings.get("probable_home_warning_only", True)),
        )


@dataclass(frozen=True)
class LearningThresholds:
    learning_promote_asn_min_support: int
    learning_promote_asn_min_precision: float
    learning_promote_combo_min_support: int
    learning_promote_combo_min_precision: float

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "LearningThresholds":
        settings = config.get("settings", {})
        return cls(
            learning_promote_asn_min_support=int(settings.get("learning_promote_asn_min_support", 10)),
            learning_promote_asn_min_precision=float(settings.get("learning_promote_asn_min_precision", 0.95)),
            learning_promote_combo_min_support=int(settings.get("learning_promote_combo_min_support", 5)),
            learning_promote_combo_min_precision=float(settings.get("learning_promote_combo_min_precision", 0.9)),
        )


@dataclass(frozen=True)
class RuntimeRuleView:
    detection: DetectionRules
    weights: ScoreWeights
    thresholds: Thresholds
    learning: LearningThresholds

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "RuntimeRuleView":
        return cls(
            detection=DetectionRules.from_config(config),
            weights=ScoreWeights.from_config(config),
            thresholds=Thresholds.from_config(config),
            learning=LearningThresholds.from_config(config),
        )
