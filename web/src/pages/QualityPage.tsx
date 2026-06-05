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
  YAxis,
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

function CustomTooltip({ active, payload, label }: any) {
  if (active && payload && payload.length) {
    return (
      <div style={{
        background: "var(--bg-panel-strong, #1f2937)",
        border: "1px solid var(--line, #374151)",
        padding: "0.75rem 1rem",
        borderRadius: "var(--radius-md, 8px)",
        boxShadow: "0 4px 20px rgba(0, 0, 0, 0.2)"
      }}>
        {label && <p style={{ fontWeight: 600, margin: "0 0 0.25rem 0", fontSize: "0.9rem" }}>{label}</p>}
        {payload.map((item: any, idx: number) => (
          <p key={idx} style={{ color: item.color || item.fill || "var(--ink)", fontSize: "0.85rem", margin: 0 }}>
            {item.name}: <strong>{item.value}</strong>
          </p>
        ))}
      </div>
    );
  }
  return null;
}

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

  const updatedBy =
    !data?.live_rules_updated_by || data.live_rules_updated_by === "bootstrap"
      ? t("common.system")
      : data.live_rules_updated_by;
  const promotedProviderTypes =
    data?.learning.promoted.by_type.filter(
      (item) =>
        item.pattern_type === "provider" ||
        item.pattern_type === "provider_service",
    ) || [];
  const legacyProviderTypes =
    data?.learning.legacy.by_type.filter(
      (item) =>
        item.pattern_type === "provider" ||
        item.pattern_type === "provider_service",
    ) || [];
  const resolutionChartData = data
    ? [
        {
          name: t("quality.cards.resolvedHome"),
          value: data.resolved_home,
          fill: "var(--success, #10b981)",
        },
        {
          name: t("quality.cards.resolvedMobile"),
          value: data.resolved_mobile,
          fill: "var(--accent, #3b82f6)",
        },
        {
          name: t("quality.cards.skipped"),
          value: data.skipped,
          fill: "var(--warning, #f59e0b)",
        },
      ]
    : [];
  const noisyAsnData =
    data?.top_noisy_asns.slice(0, 6).map((item) => ({
      name: item.asn_key,
      value: item.cnt,
    })) || [];
  const mixedProviderData =
    data?.mixed_providers.top_open_cases.slice(0, 6).map((item) => ({
      name: item.provider_key,
      open: item.open_cases,
      conflict: item.conflict_cases,
    })) || [];

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <h1>{t("quality.title")}</h1>
          <p className="page-lede">{t("quality.description")}</p>
        </div>
        <div className="action-row">
          <select
            value={moduleId}
            onChange={(event) => setModuleId(event.target.value)}
          >
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
        <div className="quality-bento-grid">
          {Array.from({ length: 6 }).map((_, index) => (
            <div className="quality-bento-item quality-span-4 skeleton-card" key={index}>
              <span className="skeleton-line short" />
              <strong className="skeleton-line medium" />
            </div>
          ))}
        </div>
      ) : null}

      {data ? (
        <>
          <div className="quality-bento-grid">
            {/* Overview Stats Block */}
            <div className="quality-bento-item quality-span-12 accent-border">
              <div className="quality-stats-strip">
                <div className="quality-stat-box highlighted">
                  <span>{t("quality.cards.openCases")}</span>
                  <strong>{data.open_cases}</strong>
                </div>
                <div className="quality-stat-box">
                  <span>{t("quality.cards.totalCases")}</span>
                  <strong>{data.total_cases}</strong>
                </div>
                <div className="quality-stat-box">
                  <span>{t("quality.cards.resolvedHome")}</span>
                  <strong>{data.resolved_home}</strong>
                </div>
                <div className="quality-stat-box">
                  <span>{t("quality.cards.resolvedMobile")}</span>
                  <strong>{data.resolved_mobile}</strong>
                </div>
                <div className="quality-stat-box">
                  <span>{t("quality.cards.skipped")}</span>
                  <strong>{data.skipped}</strong>
                </div>
                <div className="quality-stat-box">
                  <span>{t("quality.cards.activeSessions")}</span>
                  <strong>{data.active_sessions}</strong>
                </div>
              </div>
            </div>

            {/* Resolution Mix Donut */}
            <div className="quality-bento-item quality-span-4">
              <div className="panel-heading" style={{ marginBottom: "1rem" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: 700 }}>{t("quality.resolutionMixTitle")}</h2>
                <p className="muted" style={{ fontSize: "0.85rem" }}>{t("quality.resolutionMixDescription")}</p>
              </div>
              <div style={{ position: "relative", height: "220px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={resolutionChartData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={55}
                      outerRadius={80}
                      paddingAngle={4}
                    >
                      {resolutionChartData.map((entry) => (
                        <Cell key={entry.name} fill={entry.fill} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{
                  position: "absolute",
                  top: "50%",
                  left: "50%",
                  transform: "translate(-50%, -50%)",
                  textAlign: "center",
                  pointerEvents: "none"
                }}>
                  <span style={{ fontSize: "0.75rem", color: "var(--muted)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em" }}>Total</span>
                  <strong style={{ display: "block", fontSize: "1.5rem", fontWeight: 800, color: "var(--ink)" }}>{data.resolution_total}</strong>
                </div>
              </div>
            </div>

            {/* Top Noisy ASNs */}
            <div className="quality-bento-item quality-span-4">
              <div className="panel-heading" style={{ marginBottom: "1rem" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: 700 }}>{t("quality.topNoisyAsnTitle")}</h2>
                <p className="muted" style={{ fontSize: "0.85rem" }}>{t("quality.noisyAsnDescription")}</p>
              </div>
              <div style={{ height: "220px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={noisyAsnData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="noisyAsnGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--accent)" stopOpacity={1} />
                        <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.3} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 11 }} />
                    <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 11 }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="value" fill="url(#noisyAsnGrad)" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Top Mixed Providers */}
            <div className="quality-bento-item quality-span-4">
              <div className="panel-heading" style={{ marginBottom: "1rem" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: 700 }}>{t("quality.topMixedProvidersTitle")}</h2>
                <p className="muted" style={{ fontSize: "0.85rem" }}>{t("quality.mixedProvidersDescription")}</p>
              </div>
              <div style={{ height: "220px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={mixedProviderData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="openGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--success)" stopOpacity={1} />
                        <stop offset="100%" stopColor="var(--success)" stopOpacity={0.3} />
                      </linearGradient>
                      <linearGradient id="conflictGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--warning)" stopOpacity={1} />
                        <stop offset="100%" stopColor="var(--warning)" stopOpacity={0.3} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 11 }} />
                    <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 11 }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="open" fill="url(#openGrad)" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="conflict" fill="url(#conflictGrad)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Learning Thresholds */}
            <div className="quality-bento-item quality-span-6 warning-border">
              <div className="panel-heading" style={{ marginBottom: "1.25rem" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: 700 }}>{t("quality.learningStateTitle")}</h2>
                <p className="muted" style={{ fontSize: "0.85rem" }}>{t("quality.providerLearningTitle")}</p>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div className="quality-stat-box">
                  <span>{t("quality.learningCards.promotedPatterns")}</span>
                  <strong>{data.learning.promoted.active_patterns}</strong>
                </div>
                <div className="quality-stat-box">
                  <span>{t("quality.learningCards.legacyPatterns")}</span>
                  <strong>{data.learning.legacy.total_patterns}</strong>
                </div>
              </div>
              <div style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.9rem" }}>
                  <span>{t("quality.learningCards.asnMinSupport")} / Precision</span>
                  <span style={{ fontWeight: 600 }}>{data.learning.thresholds.asn_min_support} / {Math.round(data.learning.thresholds.asn_min_precision * 100)}%</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.9rem" }}>
                  <span>{t("quality.learningCards.comboMinSupport")} / Precision</span>
                  <span style={{ fontWeight: 600 }}>{data.learning.thresholds.combo_min_support} / {Math.round(data.learning.thresholds.combo_min_precision * 100)}%</span>
                </div>
              </div>
            </div>

            {/* ASN Source Information */}
            <div className="quality-bento-item quality-span-6">
              <div className="panel-heading" style={{ marginBottom: "1.25rem" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: 700 }}>{t("quality.asnSourceTitle")}</h2>
                <p className="muted" style={{ fontSize: "0.85rem" }}>{t("quality.noisyAsnDescription")}</p>
              </div>
              <div className="record-list">
                <div className="record-item" style={{ background: "var(--bg-panel-strong)", padding: "1rem" }}>
                  <div className="record-main" style={{ marginBottom: "0.5rem" }}>
                    <span className="record-title" style={{ fontSize: "1rem", fontWeight: 600 }}>
                      {data.asn_source.label}
                    </span>
                    <span className="tag" style={{ background: "var(--accent)", color: "#fff" }}>{data.asn_source.type}</span>
                  </div>
                  <div className="record-meta" style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
                    <span>
                      {data.asn_source.files.length > 0
                        ? data.asn_source.files.join(", ")
                        : t("quality.noAsnSource")}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Top Promoted Patterns */}
            <div className="quality-bento-item quality-span-6 accent-border">
              <div className="panel-heading" style={{ marginBottom: "1rem" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: 700 }}>{t("quality.topPromotedPatternsTitle")}</h2>
                <p className="muted" style={{ fontSize: "0.85rem" }}>{t("quality.learningStateTitle")}</p>
              </div>
              <div className="record-list" style={{ maxHeight: "250px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {data.learning.promoted.top_patterns.map((item) => (
                  <div
                    className="record-item"
                    key={`${item.pattern_type}:${item.pattern_value}`}
                    style={{ background: "var(--bg-panel-strong)", padding: "0.75rem 1rem", border: "1px solid var(--line)" }}
                  >
                    <div className="record-main">
                      <span className="record-title" style={{ fontWeight: 600 }}>
                        {item.pattern_type}:{item.pattern_value}
                      </span>
                      <span className="tag" style={{
                        background: item.decision === "HOME" ? "rgba(16, 185, 129, 0.15)" : "rgba(59, 130, 246, 0.15)",
                        color: item.decision === "HOME" ? "var(--success)" : "var(--accent)"
                      }}>{item.decision}</span>
                    </div>
                    <div className="record-meta" style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                      {t("quality.topPatternDetails", {
                        decision: item.decision,
                        support: item.support,
                        precision: `${Math.round(item.precision * 100)}%`,
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Top Legacy Patterns */}
            <div className="quality-bento-item quality-span-6">
              <div className="panel-heading" style={{ marginBottom: "1rem" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: 700 }}>{t("quality.topLegacyTitle")}</h2>
                <p className="muted" style={{ fontSize: "0.85rem" }}>{t("quality.learningStateTitle")}</p>
              </div>
              <div className="record-list" style={{ maxHeight: "250px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {data.learning.legacy.top_patterns.length === 0 ? (
                  <div className="provider-empty">
                    <span>{t("quality.noLegacyPatterns")}</span>
                  </div>
                ) : null}
                {data.learning.legacy.top_patterns.map((item) => (
                  <div
                    className="record-item"
                    key={`${item.pattern_type}:${item.pattern_value}:${item.decision}`}
                    style={{ background: "var(--bg-panel-strong)", padding: "0.75rem 1rem", border: "1px solid var(--line)" }}
                  >
                    <div className="record-main">
                      <span className="record-title" style={{ fontWeight: 600 }}>
                        {item.pattern_type}:{item.pattern_value}
                      </span>
                      <span className="tag" style={{
                        background: item.decision === "HOME" ? "rgba(16, 185, 129, 0.15)" : "rgba(59, 130, 246, 0.15)",
                        color: item.decision === "HOME" ? "var(--success)" : "var(--accent)"
                      }}>{item.decision}</span>
                    </div>
                    <div className="record-meta" style={{ fontSize: "0.8rem", marginTop: "0.25rem", display: "flex", justifyContent: "space-between" }}>
                      <span>
                        {t("quality.legacyConfidenceValue", {
                          value: item.confidence,
                        })}
                      </span>
                      <span>
                        {formatDisplayDateTime(
                          item.timestamp,
                          t("common.notAvailable"),
                          language,
                        )}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Provider Learning Panel */}
            <div className="quality-bento-item quality-span-12 success-border">
              <div className="panel-heading" style={{ marginBottom: "1.25rem" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: 700 }}>{t("quality.providerLearningTitle")}</h2>
                <p className="muted" style={{ fontSize: "0.85rem" }}>{t("quality.mixedProvidersDescription")}</p>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
                <div>
                  <h3 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "0.75rem", color: "var(--success)" }}>{t("quality.providerLearning.promoted")}</h3>
                  <div className="record-list" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    {promotedProviderTypes.length === 0 ? (
                      <div className="provider-empty">
                        <span>{t("quality.noPromotedData")}</span>
                      </div>
                    ) : null}
                    {promotedProviderTypes.map((item) => (
                      <div
                        className="record-item"
                        key={`provider-${item.pattern_type}`}
                        style={{ background: "var(--bg-panel-strong)", padding: "0.75rem 1rem" }}
                      >
                        <div className="record-main">
                          <span className="record-title">{item.pattern_type}</span>
                          <span className="tag" style={{ background: "var(--success)", color: "#fff" }}>{item.count}</span>
                        </div>
                        <div className="record-meta" style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                          {t("quality.patternStats", {
                            count: item.count,
                            support: item.total_support,
                            precision: `${Math.round(item.avg_precision * 100)}%`,
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "0.75rem", color: "var(--muted)" }}>{t("quality.providerLearning.legacy")}</h3>
                  <div className="record-list" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    {legacyProviderTypes.length === 0 ? (
                      <div className="provider-empty">
                        <span>{t("quality.noLegacyData")}</span>
                      </div>
                    ) : null}
                    {legacyProviderTypes.map((item) => (
                      <div
                        className="record-item"
                        key={`legacy-provider-${item.pattern_type}`}
                        style={{ background: "var(--bg-panel-strong)", padding: "0.75rem 1rem" }}
                      >
                        <div className="record-main">
                          <span className="record-title">{item.pattern_type}</span>
                          <span className="tag">{item.count}</span>
                        </div>
                        <div className="record-meta" style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                          <span>
                            {t("quality.legacyStats", {
                              count: item.count,
                              confidence: item.total_confidence,
                            })}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Pattern Type Breakdowns */}
            <div className="quality-bento-item quality-span-12">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
                <div>
                  <div className="panel-heading" style={{ marginBottom: "1rem" }}>
                    <h2 style={{ fontSize: "1.1rem", fontWeight: 700 }}>{t("quality.promotedByTypeTitle")}</h2>
                    <p className="muted" style={{ fontSize: "0.85rem" }}>{t("quality.learningStateTitle")}</p>
                  </div>
                  <div className="record-list" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    {data.learning.promoted.by_type.length === 0 ? (
                      <div className="provider-empty">
                        <span>{t("quality.noPromotedData")}</span>
                      </div>
                    ) : null}
                    {data.learning.promoted.by_type.map((item) => (
                      <div className="record-item" key={item.pattern_type} style={{ background: "var(--bg-panel-strong)", padding: "0.75rem 1rem" }}>
                        <div className="record-main">
                          <span className="record-title">{item.pattern_type}</span>
                          <span className="tag" style={{ background: "var(--accent)", color: "#fff" }}>{item.count}</span>
                        </div>
                        <div className="record-meta" style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                          {t("quality.patternStats", {
                            count: item.count,
                            support: item.total_support,
                            precision: `${Math.round(item.avg_precision * 100)}%`,
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="panel-heading" style={{ marginBottom: "1rem" }}>
                    <h2 style={{ fontSize: "1.1rem", fontWeight: 700 }}>{t("quality.legacyByTypeTitle")}</h2>
                    <p className="muted" style={{ fontSize: "0.85rem" }}>{t("quality.learningStateTitle")}</p>
                  </div>
                  <div className="record-list" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    {data.learning.legacy.by_type.length === 0 ? (
                      <div className="provider-empty">
                        <span>{t("quality.noLegacyData")}</span>
                      </div>
                    ) : null}
                    {data.learning.legacy.by_type.map((item) => (
                      <div className="record-item" key={item.pattern_type} style={{ background: "var(--bg-panel-strong)", padding: "0.75rem 1rem" }}>
                        <div className="record-main">
                          <span className="record-title">{item.pattern_type}</span>
                          <span className="tag">{item.count}</span>
                        </div>
                        <div className="record-meta" style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                          <span>
                            {t("quality.legacyStats", {
                              count: item.count,
                              confidence: item.total_confidence,
                            })}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Applied rules revision info footer panel */}
          <div className="panel compact-toolbar compact-toolbar-meta" style={{ marginTop: "1.5rem" }}>
            <span>
              {t("quality.revision", { value: data.live_rules_revision })}
            </span>
            <span>
              {t("quality.updated", {
                value: formatDisplayDateTime(
                  data.live_rules_updated_at,
                  t("common.notAvailable"),
                  language,
                ),
              })}
            </span>
            <span>{t("quality.by", { value: updatedBy })}</span>
          </div>
        </>
      ) : null}
    </section>
  );
}
