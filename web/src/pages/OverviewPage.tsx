import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { prefetchRouteModule } from "../app/routeModules";
import { api, OverviewMetricsResponse } from "../api/client";
import { useI18n } from "../localization";
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

export function OverviewPage() {
  const { t, language } = useI18n();
  const [data, setData] = useState<OverviewMetricsResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastLoadedAt, setLastLoadedAt] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const payload = await api.getOverview();
        if (cancelled) return;
        setData(payload as OverviewMetricsResponse);
        setError("");
        setLastLoadedAt(new Date().toISOString());
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("overview.errors.loadFailed"));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    const timer = window.setInterval(() => {
      void load();
    }, OVERVIEW_REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [t]);

  const health = data?.health || null;
  const quality = (data?.quality as QualityPayload | undefined) || null;
  const queue = data?.latest_cases || null;

  const systemStatusClass =
    health?.status === "ok" ? "status-resolved" : health?.status ? "severity-high" : "severity-low";

  const rulesOwner =
    !quality?.live_rules_updated_by || quality.live_rules_updated_by === "bootstrap"
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
            language
          )
        })
      : t("overview.health.updated", {
          value: formatDisplayDateTime(
            health?.core.updated_at || "",
            t("common.notAvailable"),
            language
          )
        });

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <span className="eyebrow">{t("overview.eyebrow")}</span>
          <h1>{t("overview.title")}</h1>
          <p className="page-lede">{t("overview.description")}</p>
        </div>
        <div className="dashboard-meta">
          <span className={`status-badge ${systemStatusClass}`}>{health?.status || t("common.loading")}</span>
          <span className="muted">
            {t("overview.lastUpdated", {
              value: formatDisplayDateTime(lastLoadedAt, t("common.notAvailable"), language)
            })}
          </span>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="dashboard-grid dashboard-grid-hero">
          <div className="panel panel-hero">
            <div className="panel-heading panel-heading-row">
              <div>
                <h2>{t("overview.systemStatusTitle")}</h2>
                <p className="muted">{t("overview.systemStatusDescription")}</p>
              </div>
              <span className="tag status-resolved">{t("overview.cards.core")}</span>
            </div>
          <div className="stats-grid">
            <div className="stat-card">
              <span>{t("overview.cards.openQueue")}</span>
              <strong>{queue?.count ?? "—"}</strong>
            </div>
            <div className="stat-card">
              <span>{t("overview.cards.core")}</span>
              <strong>
                {health?.core.mode === "embedded"
                  ? t("overview.cards.embeddedValue")
                  : health?.core.healthy
                    ? t("common.on")
                    : t("common.off")}
              </strong>
            </div>
            <div className="stat-card">
              <span>{t("overview.cards.ipinfo")}</span>
              <strong>{health?.ipinfo_token_present ? t("common.on") : t("common.off")}</strong>
            </div>
            <div className="stat-card">
              <span>{t("overview.cards.adminSessions")}</span>
              <strong>{health?.admin_sessions ?? "—"}</strong>
            </div>
          </div>
          <div className="hero-links">
            <Link
              to="/queue"
              className="hero-link"
              onMouseEnter={() => prefetchRouteModule("/queue")}
              onFocus={() => prefetchRouteModule("/queue")}
            >
              <span>{t("overview.quickLinks.queue")}</span>
            </Link>
            <Link
              to="/quality"
              className="hero-link"
              onMouseEnter={() => prefetchRouteModule("/quality")}
              onFocus={() => prefetchRouteModule("/quality")}
            >
              <span>{t("overview.quickLinks.quality")}</span>
            </Link>
            <Link
              to="/rules/policy"
              className="hero-link"
              onMouseEnter={() => prefetchRouteModule("/rules/policy")}
              onFocus={() => prefetchRouteModule("/rules/policy")}
            >
              <span>{t("overview.quickLinks.policy")}</span>
            </Link>
            <Link
              to="/data/exports"
              className="hero-link"
              onMouseEnter={() => prefetchRouteModule("/data/exports")}
              onFocus={() => prefetchRouteModule("/data/exports")}
            >
              <span>{t("overview.quickLinks.exports")}</span>
            </Link>
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
                <span className="record-title">{t("overview.health.core")}</span>
                <span className={`tag ${health?.core.healthy ? "status-resolved" : "severity-high"}`}>
                  {coreStatusLabel}
                </span>
              </div>
              <div className="record-meta">
                {coreRuntimeMeta}
              </div>
            </div>
            <div className="metric-row">
              <div className="record-main">
                <span className="record-title">{t("overview.health.db")}</span>
                <span className={health?.db.healthy ? "tag status-resolved" : "tag severity-high"}>
                  {health?.db.healthy ? t("common.on") : t("common.off")}
                </span>
              </div>
              <div className="record-meta">
                <span>{health?.db.path || t("common.notAvailable")}</span>
              </div>
            </div>
            <div className="metric-row">
              <div className="record-main">
                <span className="record-title">{t("overview.health.rules")}</span>
                <span>{t("rules.revision", { value: quality?.live_rules_revision ?? "—" })}</span>
              </div>
              <div className="record-meta">
                {t("overview.health.rulesBy", {
                  value: rulesOwner
                })}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="stats-grid stats-grid-emphasis">
        <div className="stat-card stat-card-emphasis">
          <span>{t("overview.cards.scoreZeroRatio")}</span>
          <strong>{health ? `${Math.round(health.analysis_24h.score_zero_ratio * 100)}%` : "—"}</strong>
        </div>
        <div className="stat-card stat-card-emphasis">
          <span>{t("overview.cards.asnMissingRatio")}</span>
          <strong>{health ? `${Math.round(health.analysis_24h.asn_missing_ratio * 100)}%` : "—"}</strong>
        </div>
        <div className="stat-card stat-card-emphasis">
          <span>{t("overview.cards.mixedConflicts")}</span>
          <strong>{quality?.mixed_providers.conflict_cases ?? "—"}</strong>
        </div>
        <div className="stat-card stat-card-emphasis">
          <span>{t("overview.cards.promotedPatterns")}</span>
          <strong>{quality?.learning.promoted.active_patterns ?? "—"}</strong>
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
                <p className="muted">{t("overview.mixedProvidersDescription")}</p>
              </div>
            </div>
            <div className="record-list">
              {quality?.mixed_providers.top_open_cases.length ? (
                quality.mixed_providers.top_open_cases.slice(0, 5).map((item) => (
                  <div className="record-item" key={item.provider_key}>
                    <div className="record-main">
                      <span className="record-title">{item.provider_key}</span>
                    </div>
                    <div className="record-grid">
                      <div className="record-kv"><strong>{t("overview.mixedProvidersMetrics.open")}</strong><span>{item.open_cases}</span></div>
                      <div className="record-kv"><strong>{t("overview.mixedProvidersMetrics.conflicts")}</strong><span>{item.conflict_cases}</span></div>
                      <div className="record-kv"><strong>{t("overview.mixedProvidersMetrics.home")}</strong><span>{item.home_cases}</span></div>
                      <div className="record-kv"><strong>{t("overview.mixedProvidersMetrics.mobile")}</strong><span>{item.mobile_cases}</span></div>
                    </div>
                    <div className="record-meta">
                      {t("overview.mixedProvidersItem", {
                        open: item.open_cases,
                        conflict: item.conflict_cases,
                        home: item.home_cases,
                        mobile: item.mobile_cases
                      })}
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
                      <span className="tag">{t("overview.noisyAsnItem", { count: item.cnt })}</span>
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
                    onMouseEnter={() => prefetchRouteModule(`/reviews/${item.id}`)}
                    onFocus={() => prefetchRouteModule(`/reviews/${item.id}`)}
                  >
                    <div className="record-main">
                      <span className="record-title">
                        #{item.id} · {item.username || item.uuid || item.ip}
                      </span>
                      <span className="tag">{item.review_reason}</span>
                    </div>
                    <div className="record-meta">
                        {item.review_reason} · {item.ip} · {formatDisplayDateTime(
                          item.updated_at,
                          t("common.notAvailable"),
                          language
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
