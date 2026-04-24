import { useState } from "react";
import { Link } from "react-router-dom";

import { hasPermission } from "../app/permissions";
import { prefetchRouteModule } from "../app/routeModules";
import { api, OverviewMetricsResponse, Session } from "../api/client";
import { useI18n } from "../localization";
import {
  automationGuardrailLabels,
  automationModeLabel,
  automationModeReasonLabels,
} from "../shared/automationStatus";
import { useVisiblePolling } from "../shared/useVisiblePolling";
import { formatDisplayDateTime } from "../utils/datetime";

type QualityPayload = {
  open_cases: number;
  total_cases: number;
  resolved_home: number;
  resolved_mobile: number;
  skipped: number;
  active_learning_patterns: number;
  active_sessions: number;
  live_rules_revision: number;
  live_rules_updated_at: string;
  live_rules_updated_by: string;
  top_noisy_asns: Array<{ asn_key: string; cnt: number }>;
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
    promoted: {
      active_patterns: number;
    };
  };
};

const OVERVIEW_REFRESH_MS = 30000;
const OVERVIEW_STALE_AFTER_SECONDS = 15;

export function OverviewPage({ session }: { session?: Session }) {
  const { t, language } = useI18n();
  const [data, setData] = useState<OverviewMetricsResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastLoadedAt, setLastLoadedAt] = useState<string>("");
  const canReadData = session ? hasPermission(session, "data.read") : true;

  async function load() {
    try {
      const payload = await api.getOverview();
      setData(payload as OverviewMetricsResponse);
      setError("");
      setLastLoadedAt(new Date().toISOString());
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("overview.errors.loadFailed"),
      );
    } finally {
      setLoading(false);
    }
  }

  useVisiblePolling(true, load, OVERVIEW_REFRESH_MS, [t]);

  const health = data?.health || null;
  const quality = (data?.quality as QualityPayload | undefined) || null;
  const queue = data?.latest_cases || null;
  const pipeline = data?.pipeline || null;
  const freshness = data?.freshness || null;
  const automationStatus = data?.automation_status || null;
  const overviewStale = Boolean(
    (freshness?.overview_age_seconds ?? 0) > OVERVIEW_STALE_AFTER_SECONDS,
  );
  const pipelineStale = Boolean(pipeline?.stale);

  const systemStatusClass =
    health?.status === "ok"
      ? "status-resolved"
      : health?.status
        ? "severity-high"
        : "severity-low";

  const rulesOwner =
    !quality?.live_rules_updated_by ||
    quality.live_rules_updated_by === "bootstrap"
      ? t("common.system")
      : quality.live_rules_updated_by;
  const coreStatusLabel =
    health?.core.mode === "embedded"
      ? t("overview.health.embedded")
      : health?.core.status || t("common.notAvailable");
  const coreRuntimeMeta =
    health?.core.mode === "embedded"
      ? t("overview.health.embeddedRuntime", {
          value: formatDisplayDateTime(
            health?.core.updated_at || "",
            t("common.notAvailable"),
            language,
          ),
        })
      : t("overview.health.updated", {
          value: formatDisplayDateTime(
            health?.core.updated_at || "",
            t("common.notAvailable"),
            language,
          ),
        });

  function formatAge(seconds?: number | null): string {
    if (seconds === null || seconds === undefined || Number.isNaN(seconds)) {
      return t("common.notAvailable");
    }
    const total = Math.max(Math.round(seconds), 0);
    if (total < 60) return `${total}s`;
    if (total < 3600) return `${Math.round(total / 60)}m`;
    return `${Math.round(total / 3600)}h`;
  }

  const attentionItems: string[] = [];
  if (overviewStale) {
    attentionItems.push(t("overview.attentionItems.overviewStale"));
  }
  if (pipelineStale) {
    attentionItems.push(t("overview.attentionItems.pipelineStale"));
  }
  if ((pipeline?.failed_count ?? 0) > 0) {
    attentionItems.push(
      t("overview.attentionItems.failedQueue", {
        count: pipeline?.failed_count ?? 0,
      }),
    );
  }
  if ((quality?.open_cases ?? 0) > 0) {
    attentionItems.push(
      t("overview.attentionItems.openCases", {
        count: quality?.open_cases ?? 0,
      }),
    );
  }
  if ((quality?.mixed_providers.conflict_cases ?? 0) > 0) {
    attentionItems.push(
      t("overview.attentionItems.mixedConflicts", {
        count: quality?.mixed_providers.conflict_cases ?? 0,
      }),
    );
  }
  if (!attentionItems.length) {
    attentionItems.push(t("overview.attentionItems.quiet"));
  }
  const automationModeReasons = automationModeReasonLabels(t, automationStatus);
  const automationGuardrails = automationGuardrailLabels(t, automationStatus);

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <h1>{t("overview.title")}</h1>
          <p className="page-lede">{t("overview.description")}</p>
          <span className={`status-badge ${systemStatusClass}`}>
            {health?.status || t("common.loading")}
          </span>
          <div className="overview-pipeline-grid">
            {overviewStale ? (
              <span className="tag severity-high">
                {t("overview.snapshotStale")}
              </span>
            ) : null}
            {pipelineStale ? (
              <span className="tag severity-high">
                {t("overview.pipeline.stale")}
              </span>
            ) : null}
          </div>
        </div>
        <div className="dashboard-meta">
          <span className="muted">
            {t("overview.lastUpdated", {
              value: formatDisplayDateTime(
                freshness?.overview_updated_at || lastLoadedAt,
                t("common.notAvailable"),
                language,
              ),
            })}
          </span>
        </div>
      </div>

      {error ? (
        <div className="error-box">
          {error}
          {data
            ? ` ${t("overview.errors.showingLastGood", {
                value: formatAge(freshness?.overview_age_seconds),
              })}`
            : ""}
        </div>
      ) : null}

      <div className="dashboard-grid dashboard-grid-hero">
        <div className="panel panel-hero overview-attention-panel">
          <div className="panel-heading panel-heading-row">
            <div>
              <h2>{t("overview.attentionTitle")}</h2>
              <p className="muted">{t("overview.attentionDescription")}</p>
            </div>
          </div>
          <div className="stats-grid">
            <div className="stat-card">
              <span>{t("overview.cards.openQueue")}</span>
              <strong>{quality?.open_cases ?? queue?.count ?? "—"}</strong>
            </div>
            <div className="stat-card">
              <span>{t("overview.cards.failedQueue")}</span>
              <strong>{pipeline?.failed_count ?? "—"}</strong>
            </div>
            <div className="stat-card">
              <span>{t("overview.cards.mixedConflicts")}</span>
              <strong>{quality?.mixed_providers.conflict_cases ?? "—"}</strong>
            </div>
            <div className="stat-card">
              <span>{t("overview.cards.promotedPatterns")}</span>
              <strong>
                {quality?.learning.promoted.active_patterns ?? "—"}
              </strong>
            </div>
            <div className="stat-card">
              <span>{t("overview.cards.automationMode")}</span>
              <strong>{automationModeLabel(t, automationStatus)}</strong>
            </div>
          </div>
          <div className="record-list overview-signal-list">
            {attentionItems.map((item) => (
              <div className="record-item" key={item}>
                <div className="record-main">
                  <span className="record-title">{item}</span>
                </div>
              </div>
            ))}
          </div>
          <div className="dashboard-grid overview-pipeline-grid">
            <div className="metric-list">
              <div className="metric-row">
                <div className="record-main">
                  <span className="record-title">
                    {t("overview.pipeline.queueDepth")}
                  </span>
                  <span>{pipeline?.queue_depth ?? "—"}</span>
                </div>
                <div className="record-meta">
                  {t("overview.pipeline.queueMeta", {
                    queued: pipeline?.queued_count ?? 0,
                    processing: pipeline?.processing_count ?? 0,
                  })}
                </div>
              </div>
              <div className="metric-row">
                <div className="record-main">
                  <span className="record-title">
                    {t("overview.pipeline.failed")}
                  </span>
                  <span>{pipeline?.failed_count ?? "—"}</span>
                </div>
                <div className="record-meta">
                  {t("overview.pipeline.pendingRemote", {
                    count: pipeline?.enforcement_pending_count ?? 0,
                  })}
                </div>
              </div>
            </div>
            <div className="metric-list">
              <div className="metric-row">
                <div className="record-main">
                  <span className="record-title">
                    {t("overview.pipeline.lag")}
                  </span>
                  <span>{formatAge(pipeline?.current_lag_seconds)}</span>
                </div>
                <div className="record-meta">
                  {t("overview.pipeline.oldestQueued", {
                    value: formatAge(pipeline?.oldest_queued_age_seconds),
                  })}
                </div>
              </div>
              <div className="metric-row">
                <div className="record-main">
                  <span className="record-title">
                    {t("overview.pipeline.lastDrain")}
                  </span>
                  <span>
                    {formatDisplayDateTime(
                      pipeline?.last_successful_drain_at || "",
                      t("common.notAvailable"),
                      language,
                    )}
                  </span>
                </div>
                <div className="record-meta">
                  {formatDisplayDateTime(
                    pipeline?.snapshot_updated_at ||
                      freshness?.pipeline_updated_at ||
                      "",
                    t("common.notAvailable"),
                    language,
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="panel">
          <div className="panel-heading panel-heading-row">
            <div>
              <h2>{t("overview.healthTitle")}</h2>
              <p className="muted">{t("overview.healthDescription")}</p>
            </div>
          </div>
          <div className="metric-list">
            <div className="metric-row">
              <div className="record-main">
                <span className="record-title">
                  {t("overview.health.core")}
                </span>
                <span
                  className={`tag ${health?.core.healthy ? "status-resolved" : "severity-high"}`}
                >
                  {coreStatusLabel}
                </span>
              </div>
              <div className="record-meta">{coreRuntimeMeta}</div>
            </div>
            <div className="metric-row">
              <div className="record-main">
                <span className="record-title">{t("overview.health.db")}</span>
                <span
                  className={
                    health?.db.healthy
                      ? "tag status-resolved"
                      : "tag severity-high"
                  }
                >
                  {health?.db.healthy ? t("common.on") : t("common.off")}
                </span>
              </div>
              <div className="record-meta">
                <span>{health?.db.path || t("common.notAvailable")}</span>
              </div>
            </div>
            <div className="metric-row">
              <div className="record-main">
                <span className="record-title">
                  {t("overview.health.rules")}
                </span>
                <span>
                  {t("rules.revision", {
                    value: quality?.live_rules_revision ?? "—",
                  })}
                </span>
              </div>
              <div className="record-meta">
                {t("overview.health.rulesBy", {
                  value: rulesOwner,
                })}
              </div>
            </div>
            <div className="metric-row">
              <div className="record-main">
                <span className="record-title">
                  {t("overview.cards.adminSessions")}
                </span>
                <span>{health?.admin_sessions ?? "—"}</span>
              </div>
              <div className="record-meta">
                {t("overview.cards.ipinfo")} ·{" "}
                {health?.ipinfo_token_present
                  ? t("common.on")
                  : t("common.off")}
              </div>
            </div>
            <div className="metric-row">
              <div className="record-main">
                <span className="record-title">
                  {t("overview.cards.scoreZeroRatio")}
                </span>
                <span>
                  {health
                    ? `${Math.round(health.analysis_24h.score_zero_ratio * 100)}%`
                    : "—"}
                </span>
              </div>
              <div className="record-meta">
                {t("overview.cards.asnMissingRatio")} ·{" "}
                {health
                  ? `${Math.round(health.analysis_24h.asn_missing_ratio * 100)}%`
                  : "—"}
              </div>
            </div>
            <div className="metric-row">
              <div className="record-main">
                <span className="record-title">
                  {t("overview.automation.modeTitle")}
                </span>
                <span>{automationModeLabel(t, automationStatus)}</span>
              </div>
              <div className="record-meta">
                {automationModeReasons.length > 0
                  ? automationModeReasons.join(", ")
                  : t("overview.automation.noModeReasons")}
              </div>
            </div>
            <div className="metric-row">
              <div className="record-main">
                <span className="record-title">
                  {t("overview.automation.guardrailsTitle")}
                </span>
                <span>{automationGuardrails.length}</span>
              </div>
              <div className="record-meta">
                {automationGuardrails.length > 0
                  ? automationGuardrails.join(", ")
                  : t("overview.automation.noGuardrails")}
              </div>
            </div>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="dashboard-grid">
          {Array.from({ length: 3 }).map((_, index) => (
            <div className="panel skeleton-card" key={index}>
              <div className="loading-stack">
                <span className="skeleton-line medium" />
                <span className="skeleton-line long" />
                <span className="skeleton-line long" />
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {!loading ? (
        <div className="dashboard-grid">
          <div className="panel">
            <div className="panel-heading panel-heading-row">
              <div>
                <h2>{t("overview.mixedProvidersTitle")}</h2>
                <p className="muted">
                  {t("overview.mixedProvidersDescription")}
                </p>
              </div>
            </div>
            <div className="record-list">
              {quality?.mixed_providers.top_open_cases.length ? (
                quality.mixed_providers.top_open_cases
                  .slice(0, 5)
                  .map((item) => (
                    <div className="record-item" key={item.provider_key}>
                      <div className="record-main">
                        <span className="record-title">
                          {item.provider_key}
                        </span>
                      </div>
                      <div className="record-grid">
                        <div className="record-kv">
                          <strong>
                            {t("overview.mixedProvidersMetrics.open")}
                          </strong>
                          <span>{item.open_cases}</span>
                        </div>
                        <div className="record-kv">
                          <strong>
                            {t("overview.mixedProvidersMetrics.conflicts")}
                          </strong>
                          <span>{item.conflict_cases}</span>
                        </div>
                        <div className="record-kv">
                          <strong>
                            {t("overview.mixedProvidersMetrics.home")}
                          </strong>
                          <span>{item.home_cases}</span>
                        </div>
                        <div className="record-kv">
                          <strong>
                            {t("overview.mixedProvidersMetrics.mobile")}
                          </strong>
                          <span>{item.mobile_cases}</span>
                        </div>
                      </div>
                    </div>
                  ))
              ) : (
                <div className="provider-empty">
                  <span>{t("overview.emptyMixedProviders")}</span>
                </div>
              )}
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading panel-heading-row">
              <div>
                <h2>{t("overview.noisyAsnTitle")}</h2>
                <p className="muted">{t("overview.noisyAsnDescription")}</p>
              </div>
            </div>
            <div className="record-list">
              {quality?.top_noisy_asns.length ? (
                quality.top_noisy_asns.slice(0, 6).map((item) => (
                  <div className="record-item" key={item.asn_key}>
                    <div className="record-main">
                      <span className="record-title">{item.asn_key}</span>
                      <span className="tag">
                        {t("overview.noisyAsnItem", { count: item.cnt })}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="provider-empty">
                  <span>{t("overview.emptyNoisyAsn")}</span>
                </div>
              )}
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading panel-heading-row">
              <div>
                <h2>{t("overview.latestCasesTitle")}</h2>
                <p className="muted">{t("overview.latestCasesDescription")}</p>
              </div>
            </div>
            <div className="record-list">
              {queue?.items.length ? (
                queue.items.map((item) => (
                  <Link
                    to={`/reviews/${item.id}`}
                    className="record-item inline-link"
                    key={item.id}
                    onMouseEnter={() =>
                      prefetchRouteModule(`/reviews/${item.id}`)
                    }
                    onFocus={() => prefetchRouteModule(`/reviews/${item.id}`)}
                  >
                    <div className="record-main">
                      <span className="record-title">
                        #{item.id} · {item.username || item.uuid || item.ip}
                      </span>
                      <span className="tag">{item.review_reason}</span>
                    </div>
                    <div className="record-meta">
                      {item.review_reason} · {item.ip} ·{" "}
                      {formatDisplayDateTime(
                        item.updated_at,
                        t("common.notAvailable"),
                        language,
                      )}
                    </div>
                  </Link>
                ))
              ) : (
                <div className="provider-empty">
                  <span>{t("overview.emptyLatestCases")}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
