import { useEffect, useState } from "react";

import { api } from "../api/client";
import { useI18n } from "../localization";
import { formatDisplayDateTime } from "../utils/datetime";

type PromotedLearningTypeSummary = {
  pattern_type: string;
  count: number;
  total_support: number;
  avg_precision: number;
};

type PromotedPattern = {
  pattern_type: string;
  pattern_value: string;
  decision: string;
  support: number;
  precision: number;
};

type LegacyLearningTypeSummary = {
  pattern_type: string;
  count: number;
  total_confidence: number;
};

type LegacyLearningPattern = {
  pattern_type: string;
  pattern_value: string;
  decision: string;
  confidence: number;
  timestamp: string;
};

type QualityPayload = {
  open_cases: number;
  total_cases: number;
  resolved_home: number;
  resolved_mobile: number;
  skipped: number;
  resolution_total: number;
  active_learning_patterns: number;
  active_sessions: number;
  live_rules_revision: number;
  live_rules_updated_at: string;
  live_rules_updated_by: string;
  top_noisy_asns: Array<{ asn_key: string; cnt: number }>;
  top_patterns: PromotedPattern[];
  asn_source: {
    type: string;
    label: string;
    files: string[];
  };
  learning: {
    thresholds: {
      asn_min_support: number;
      asn_min_precision: number;
      combo_min_support: number;
      combo_min_precision: number;
    };
    promoted: {
      active_patterns: number;
      by_type: PromotedLearningTypeSummary[];
      top_patterns: PromotedPattern[];
    };
    legacy: {
      total_patterns: number;
      total_confidence: number;
      by_type: LegacyLearningTypeSummary[];
      top_patterns: LegacyLearningPattern[];
    };
  };
};

export function QualityPage() {
  const { t, language } = useI18n();
  const [data, setData] = useState<QualityPayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getQuality()
      .then((payload) => setData(payload as QualityPayload))
      .catch((err: Error) => setError(err.message || t("quality.loadFailed")));
  }, [t]);

  const updatedBy = !data?.live_rules_updated_by || data.live_rules_updated_by === "bootstrap"
    ? t("common.system")
    : data.live_rules_updated_by;

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">{t("quality.eyebrow")}</span>
          <h1>{t("quality.title")}</h1>
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      {!data ? <div className="panel">{t("common.loading")}</div> : null}

      {data ? (
        <>
          <div className="stats-grid">
            <div className="stat-card"><span>{t("quality.cards.openCases")}</span><strong>{data.open_cases}</strong></div>
            <div className="stat-card"><span>{t("quality.cards.totalCases")}</span><strong>{data.total_cases}</strong></div>
            <div className="stat-card"><span>{t("quality.cards.resolvedHome")}</span><strong>{data.resolved_home}</strong></div>
            <div className="stat-card"><span>{t("quality.cards.resolvedMobile")}</span><strong>{data.resolved_mobile}</strong></div>
            <div className="stat-card"><span>{t("quality.cards.skipped")}</span><strong>{data.skipped}</strong></div>
            <div className="stat-card"><span>{t("quality.cards.activePatterns")}</span><strong>{data.active_learning_patterns}</strong></div>
            <div className="stat-card"><span>{t("quality.cards.activeSessions")}</span><strong>{data.active_sessions}</strong></div>
            <div className="stat-card">
              <span>{t("quality.cards.homeRatio")}</span>
              <strong>
                {data.resolution_total > 0
                  ? `${Math.round((data.resolved_home / data.resolution_total) * 100)}%`
                  : "0%"}
              </strong>
            </div>
            <div className="stat-card">
              <span>{t("quality.cards.mobileRatio")}</span>
              <strong>
                {data.resolution_total > 0
                  ? `${Math.round((data.resolved_mobile / data.resolution_total) * 100)}%`
                  : "0%"}
              </strong>
            </div>
          </div>
          <div className="panel queue-footer">
            <span>{t("quality.revision", { value: data.live_rules_revision })}</span>
            <span>{t("quality.updated", { value: formatDisplayDateTime(data.live_rules_updated_at, t("common.notAvailable"), language) })}</span>
            <span>{t("quality.by", { value: updatedBy })}</span>
          </div>
          <div className="panel">
            <h2>{t("quality.asnSourceTitle")}</h2>
            <ul className="reason-list">
              <li>
                <strong>{data.asn_source.label}</strong>
                <span>{data.asn_source.type}</span>
                <span>{data.asn_source.files.length > 0 ? data.asn_source.files.join(", ") : t("quality.noAsnSource")}</span>
              </li>
            </ul>
          </div>
          <div className="panel">
            <h2>{t("quality.topNoisyAsnTitle")}</h2>
            <ul className="reason-list">
              {data.top_noisy_asns.map((item) => (
                <li key={item.asn_key}>
                  <strong>{item.asn_key}</strong>
                  <span>{t("quality.reviewCases", { count: item.cnt })}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="panel">
            <h2>{t("quality.topPromotedPatternsTitle")}</h2>
            <ul className="reason-list">
              {data.learning.promoted.top_patterns.map((item) => (
                <li key={`${item.pattern_type}:${item.pattern_value}`}>
                  <strong>{item.pattern_type}:{item.pattern_value}</strong>
                  <span>
                    {t("quality.topPatternDetails", {
                      decision: item.decision,
                      support: item.support,
                      precision: `${Math.round(item.precision * 100)}%`
                    })}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="panel">
            <h2>{t("quality.learningStateTitle")}</h2>
            <div className="stats-grid">
              <div className="stat-card">
                <span>{t("quality.learningCards.promotedPatterns")}</span>
                <strong>{data.learning.promoted.active_patterns}</strong>
              </div>
              <div className="stat-card">
                <span>{t("quality.learningCards.legacyPatterns")}</span>
                <strong>{data.learning.legacy.total_patterns}</strong>
              </div>
              <div className="stat-card">
                <span>{t("quality.learningCards.legacyConfidence")}</span>
                <strong>{data.learning.legacy.total_confidence}</strong>
              </div>
              <div className="stat-card">
                <span>{t("quality.learningCards.asnMinSupport")}</span>
                <strong>{data.learning.thresholds.asn_min_support}</strong>
              </div>
              <div className="stat-card">
                <span>{t("quality.learningCards.asnMinPrecision")}</span>
                <strong>{Math.round(data.learning.thresholds.asn_min_precision * 100)}%</strong>
              </div>
              <div className="stat-card">
                <span>{t("quality.learningCards.comboMinSupport")}</span>
                <strong>{data.learning.thresholds.combo_min_support}</strong>
              </div>
              <div className="stat-card">
                <span>{t("quality.learningCards.comboMinPrecision")}</span>
                <strong>{Math.round(data.learning.thresholds.combo_min_precision * 100)}%</strong>
              </div>
            </div>
          </div>
          <div className="panel">
            <h2>{t("quality.promotedByTypeTitle")}</h2>
            <ul className="reason-list">
              {data.learning.promoted.by_type.length === 0 ? <li><span>{t("quality.noPromotedData")}</span></li> : null}
              {data.learning.promoted.by_type.map((item) => (
                <li key={item.pattern_type}>
                  <strong>{item.pattern_type}</strong>
                  <span>
                    {t("quality.patternStats", {
                      count: item.count,
                      support: item.total_support,
                      precision: `${Math.round(item.avg_precision * 100)}%`
                    })}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="panel">
            <h2>{t("quality.legacyByTypeTitle")}</h2>
            <ul className="reason-list">
              {data.learning.legacy.by_type.length === 0 ? <li><span>{t("quality.noLegacyData")}</span></li> : null}
              {data.learning.legacy.by_type.map((item) => (
                <li key={item.pattern_type}>
                  <strong>{item.pattern_type}</strong>
                  <span>{t("quality.legacyStats", { count: item.count, confidence: item.total_confidence })}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="panel">
            <h2>{t("quality.topLegacyTitle")}</h2>
            <ul className="reason-list">
              {data.learning.legacy.top_patterns.length === 0 ? <li><span>{t("quality.noLegacyPatterns")}</span></li> : null}
              {data.learning.legacy.top_patterns.map((item) => (
                <li key={`${item.pattern_type}:${item.pattern_value}:${item.decision}`}>
                  <strong>{item.pattern_type}:{item.pattern_value}</strong>
                  <span>
                    {item.decision} · confidence {item.confidence}
                  </span>
                  <span>{formatDisplayDateTime(item.timestamp, t("common.notAvailable"), language)}</span>
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : null}
    </section>
  );
}
