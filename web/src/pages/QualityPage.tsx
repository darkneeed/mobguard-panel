import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

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
  selected_module_id?: string | null;
  modules: Array<{
    module_id: string;
    module_name: string;
    status: string;
    version: string;
    protocol_version: string;
    config_revision_applied: number;
    last_seen_at: string;
  }>;
  mixed_providers: {
    open_cases: number;
    conflict_cases: number;
    conflict_rate: number;
    top_open_cases: Array<{
      provider_key: string;
      open_cases: number;
      conflict_cases: number;
      home_cases: number;
      mobile_cases: number;
      unsure_cases: number;
    }>;
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
  const [moduleId, setModuleId] = useState("");

  useEffect(() => {
    api
      .getQuality(moduleId ? { module_id: moduleId } : {})
      .then((payload) => setData(payload as QualityPayload))
      .catch((err: Error) => setError(err.message || t("quality.loadFailed")));
  }, [moduleId, t]);

  const updatedBy = !data?.live_rules_updated_by || data.live_rules_updated_by === "bootstrap"
    ? t("common.system")
    : data.live_rules_updated_by;
  const promotedProviderTypes = data?.learning.promoted.by_type.filter((item) =>
    item.pattern_type === "provider" || item.pattern_type === "provider_service"
  ) || [];
  const legacyProviderTypes = data?.learning.legacy.by_type.filter((item) =>
    item.pattern_type === "provider" || item.pattern_type === "provider_service"
  ) || [];
  const resolutionChartData = data
    ? [
        { name: t("quality.cards.resolvedHome"), value: data.resolved_home, fill: "#0f766e" },
        { name: t("quality.cards.resolvedMobile"), value: data.resolved_mobile, fill: "#155e75" },
        { name: t("quality.cards.skipped"), value: data.skipped, fill: "#c77d1a" }
      ]
    : [];
  const noisyAsnData = data?.top_noisy_asns.slice(0, 6).map((item) => ({
    name: item.asn_key,
    value: item.cnt
  })) || [];
  const mixedProviderData = data?.mixed_providers.top_open_cases.slice(0, 6).map((item) => ({
    name: item.provider_key,
    open: item.open_cases,
    conflict: item.conflict_cases
  })) || [];

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <span className="eyebrow">{t("quality.eyebrow")}</span>
          <h1>{t("quality.title")}</h1>
          <p className="page-lede">{t("quality.description")}</p>
        </div>
        <div className="action-row">
          <select value={moduleId} onChange={(event) => setModuleId(event.target.value)}>
            <option value="">{t("quality.allModules")}</option>
            {(data?.modules || []).map((item) => (
              <option key={item.module_id} value={item.module_id}>
                {item.module_name || item.module_id}
              </option>
            ))}
          </select>
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      {!data ? (
        <div className="stats-grid">
          {Array.from({ length: 6 }).map((_, index) => (
            <div className="stat-card skeleton-card" key={index}>
              <span className="skeleton-line short" />
              <strong className="skeleton-line medium" />
            </div>
          ))}
        </div>
      ) : null}

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
            <div className="stat-card"><span>{t("quality.cards.mixedProviderCases")}</span><strong>{data.mixed_providers.open_cases}</strong></div>
            <div className="stat-card"><span>{t("quality.cards.mixedConflictRate")}</span><strong>{Math.round(data.mixed_providers.conflict_rate * 100)}%</strong></div>
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
          <div className="panel compact-toolbar compact-toolbar-meta">
            <span>{t("quality.revision", { value: data.live_rules_revision })}</span>
            <span>{t("quality.updated", { value: formatDisplayDateTime(data.live_rules_updated_at, t("common.notAvailable"), language) })}</span>
            <span>{t("quality.by", { value: updatedBy })}</span>
          </div>
          <div className="dashboard-grid">
            <div className="panel chart-panel">
              <div className="panel-heading">
                <h2>{t("quality.resolutionMixTitle")}</h2>
                <p className="muted">{t("quality.resolutionMixDescription")}</p>
              </div>
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={resolutionChartData} dataKey="value" nameKey="name" innerRadius={56} outerRadius={88}>
                    {resolutionChartData.map((entry) => (
                      <Cell key={entry.name} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="panel chart-panel">
              <div className="panel-heading">
                <h2>{t("quality.topNoisyAsnTitle")}</h2>
                <p className="muted">{t("quality.noisyAsnDescription")}</p>
              </div>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={noisyAsnData}>
                  <XAxis dataKey="name" tickLine={false} axisLine={false} />
                  <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#155e75" radius={[10, 10, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="panel chart-panel">
              <div className="panel-heading">
                <h2>{t("quality.topMixedProvidersTitle")}</h2>
                <p className="muted">{t("quality.mixedProvidersDescription")}</p>
              </div>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={mixedProviderData}>
                  <XAxis dataKey="name" tickLine={false} axisLine={false} />
                  <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                  <Tooltip />
                  <Bar dataKey="open" fill="#0f766e" radius={[10, 10, 0, 0]} />
                  <Bar dataKey="conflict" fill="#c77d1a" radius={[10, 10, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="dashboard-grid">
            <div className="panel">
              <div className="panel-heading">
                <h2>{t("quality.asnSourceTitle")}</h2>
                <p className="muted">{t("quality.noisyAsnDescription")}</p>
              </div>
              <div className="record-list">
                <div className="record-item">
                  <div className="record-main">
                    <span className="record-title">{data.asn_source.label}</span>
                    <span className="tag">{data.asn_source.type}</span>
                  </div>
                  <div className="record-meta">
                    <span>{data.asn_source.files.length > 0 ? data.asn_source.files.join(", ") : t("quality.noAsnSource")}</span>
                  </div>
                </div>
              </div>
            </div>
            <div className="panel">
              <div className="panel-heading">
                <h2>{t("quality.topPromotedPatternsTitle")}</h2>
                <p className="muted">{t("quality.learningStateTitle")}</p>
              </div>
              <div className="record-list">
                {data.learning.promoted.top_patterns.map((item) => (
                  <div className="record-item" key={`${item.pattern_type}:${item.pattern_value}`}>
                    <div className="record-main">
                      <span className="record-title">{item.pattern_type}:{item.pattern_value}</span>
                      <span className="tag">{item.decision}</span>
                    </div>
                    <div className="record-meta">
                      {t("quality.topPatternDetails", {
                        decision: item.decision,
                        support: item.support,
                        precision: `${Math.round(item.precision * 100)}%`
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="panel">
            <div className="panel-heading">
              <h2>{t("quality.learningStateTitle")}</h2>
              <p className="muted">{t("quality.providerLearningTitle")}</p>
            </div>
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
          <div className="detail-grid">
          <div className="panel">
            <div className="panel-heading">
              <h2>{t("quality.promotedByTypeTitle")}</h2>
              <p className="muted">{t("quality.learningStateTitle")}</p>
            </div>
            <div className="record-list">
              {data.learning.promoted.by_type.length === 0 ? <div className="provider-empty"><span>{t("quality.noPromotedData")}</span></div> : null}
              {data.learning.promoted.by_type.map((item) => (
                <div className="record-item" key={item.pattern_type}>
                  <div className="record-main">
                    <span className="record-title">{item.pattern_type}</span>
                    <span className="tag">{item.count}</span>
                  </div>
                  <div className="record-meta">
                    {t("quality.patternStats", {
                      count: item.count,
                      support: item.total_support,
                      precision: `${Math.round(item.avg_precision * 100)}%`
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="panel">
            <div className="panel-heading">
              <h2>{t("quality.legacyByTypeTitle")}</h2>
              <p className="muted">{t("quality.learningStateTitle")}</p>
            </div>
            <div className="record-list">
              {data.learning.legacy.by_type.length === 0 ? <div className="provider-empty"><span>{t("quality.noLegacyData")}</span></div> : null}
              {data.learning.legacy.by_type.map((item) => (
                <div className="record-item" key={item.pattern_type}>
                  <div className="record-main">
                    <span className="record-title">{item.pattern_type}</span>
                    <span className="tag">{item.count}</span>
                  </div>
                  <div className="record-meta">
                    <span>{t("quality.legacyStats", { count: item.count, confidence: item.total_confidence })}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
          </div>
          <div className="panel">
            <div className="panel-heading">
              <h2>{t("quality.providerLearningTitle")}</h2>
              <p className="muted">{t("quality.mixedProvidersDescription")}</p>
            </div>
            <div className="detail-grid">
              <div className="panel">
                <h3>{t("quality.providerLearning.promoted")}</h3>
                <div className="record-list">
                  {promotedProviderTypes.length === 0 ? <div className="provider-empty"><span>{t("quality.noPromotedData")}</span></div> : null}
                  {promotedProviderTypes.map((item) => (
                    <div className="record-item" key={`provider-${item.pattern_type}`}>
                      <div className="record-main">
                        <span className="record-title">{item.pattern_type}</span>
                        <span className="tag">{item.count}</span>
                      </div>
                      <div className="record-meta">
                        {t("quality.patternStats", {
                          count: item.count,
                          support: item.total_support,
                          precision: `${Math.round(item.avg_precision * 100)}%`
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="panel">
                <h3>{t("quality.providerLearning.legacy")}</h3>
                <div className="record-list">
                  {legacyProviderTypes.length === 0 ? <div className="provider-empty"><span>{t("quality.noLegacyData")}</span></div> : null}
                  {legacyProviderTypes.map((item) => (
                    <div className="record-item" key={`legacy-provider-${item.pattern_type}`}>
                      <div className="record-main">
                        <span className="record-title">{item.pattern_type}</span>
                        <span className="tag">{item.count}</span>
                      </div>
                      <div className="record-meta">
                        <span>{t("quality.legacyStats", { count: item.count, confidence: item.total_confidence })}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <div className="panel">
            <div className="panel-heading">
              <h2>{t("quality.topLegacyTitle")}</h2>
              <p className="muted">{t("quality.learningStateTitle")}</p>
            </div>
            <div className="record-list">
              {data.learning.legacy.top_patterns.length === 0 ? <div className="provider-empty"><span>{t("quality.noLegacyPatterns")}</span></div> : null}
              {data.learning.legacy.top_patterns.map((item) => (
                <div className="record-item" key={`${item.pattern_type}:${item.pattern_value}:${item.decision}`}>
                  <div className="record-main">
                    <span className="record-title">{item.pattern_type}:{item.pattern_value}</span>
                    <span className="tag">{item.decision}</span>
                  </div>
                  <div className="record-meta">
                    <span>{t("quality.legacyConfidenceValue", { value: item.confidence })}</span>
                    <span>{formatDisplayDateTime(item.timestamp, t("common.notAvailable"), language)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
