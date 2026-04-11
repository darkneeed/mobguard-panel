import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, ReviewListResponse } from "../api/client";
import { useI18n } from "../localization";
import { formatDisplayDateTime } from "../utils/datetime";

type HealthSnapshot = {
  status: string;
  admin_sessions: number;
  ipinfo_token_present: boolean;
  db: {
    healthy: boolean;
    path: string;
  };
  core: {
    healthy: boolean;
    status: string;
    updated_at?: string;
    age_seconds?: number;
    details?: Record<string, unknown>;
  };
  live_rules: {
    revision: number;
    updated_at: string;
    updated_by: string;
  };
  analysis_24h: {
    total: number;
    score_zero_count: number;
    score_zero_ratio: number;
    asn_missing_count: number;
    asn_missing_ratio: number;
  };
};

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
  const [health, setHealth] = useState<HealthSnapshot | null>(null);
  const [quality, setQuality] = useState<QualityPayload | null>(null);
  const [queue, setQueue] = useState<ReviewListResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastLoadedAt, setLastLoadedAt] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [healthPayload, qualityPayload, queuePayload] = await Promise.all([
          api.getHealth(),
          api.getQuality(),
          api.listReviews({ status: "OPEN", page: 1, page_size: 6, sort: "updated_desc" })
        ]);
        if (cancelled) return;
        setHealth(healthPayload as HealthSnapshot);
        setQuality(qualityPayload as QualityPayload);
        setQueue(queuePayload);
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

  const systemStatusClass =
    health?.status === "ok" ? "status-resolved" : health?.status ? "severity-high" : "severity-low";

  const rulesOwner =
    !quality?.live_rules_updated_by || quality.live_rules_updated_by === "bootstrap"
      ? t("common.system")
      : quality.live_rules_updated_by;

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
              <strong>{health?.core.healthy ? t("common.on") : t("common.off")}</strong>
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
            <Link to="/queue" className="hero-link">
              <span>{t("overview.quickLinks.queue")}</span>
            </Link>
            <Link to="/quality" className="hero-link">
              <span>{t("overview.quickLinks.quality")}</span>
            </Link>
            <Link to="/rules/policy" className="hero-link">
              <span>{t("overview.quickLinks.policy")}</span>
            </Link>
            <Link to="/data/exports" className="hero-link">
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
            <span className="tag">{t("overview.healthTitle")}</span>
          </div>
          <ul className="reason-list overview-health-list">
            <li>
              <strong>{t("overview.health.core")}</strong>
              <span>{health?.core.status || t("common.notAvailable")}</span>
              <span>
                {t("overview.health.updated", {
                  value: formatDisplayDateTime(
                    health?.core.updated_at || "",
                    t("common.notAvailable"),
                    language
                  )
                })}
              </span>
            </li>
            <li>
              <strong>{t("overview.health.db")}</strong>
              <span>{health?.db.healthy ? t("common.on") : t("common.off")}</span>
              <span>{health?.db.path || t("common.notAvailable")}</span>
            </li>
            <li>
              <strong>{t("overview.health.rules")}</strong>
              <span>{t("rules.revision", { value: quality?.live_rules_revision ?? "—" })}</span>
              <span>
                {t("overview.health.rulesBy", {
                  value: rulesOwner
                })}
              </span>
            </li>
          </ul>
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
              <span className="tag">{t("overview.mixedProvidersTitle")}</span>
            </div>
            <ul className="reason-list">
              {quality?.mixed_providers.top_open_cases.length ? (
                quality.mixed_providers.top_open_cases.slice(0, 5).map((item) => (
                  <li key={item.provider_key}>
                    <strong>{item.provider_key}</strong>
                    <span>
                      {t("overview.mixedProvidersItem", {
                        open: item.open_cases,
                        conflict: item.conflict_cases,
                        home: item.home_cases,
                        mobile: item.mobile_cases
                      })}
                    </span>
                  </li>
                ))
              ) : (
                <li>
                  <span>{t("overview.emptyMixedProviders")}</span>
                </li>
              )}
            </ul>
          </div>

          <div className="panel">
            <div className="panel-heading panel-heading-row">
              <div>
                <h2>{t("overview.noisyAsnTitle")}</h2>
                <p className="muted">{t("overview.noisyAsnDescription")}</p>
              </div>
              <span className="tag">{t("overview.noisyAsnTitle")}</span>
            </div>
            <ul className="reason-list">
              {quality?.top_noisy_asns.length ? (
                quality.top_noisy_asns.slice(0, 6).map((item) => (
                  <li key={item.asn_key}>
                    <strong>{item.asn_key}</strong>
                    <span>{t("overview.noisyAsnItem", { count: item.cnt })}</span>
                  </li>
                ))
              ) : (
                <li>
                  <span>{t("overview.emptyNoisyAsn")}</span>
                </li>
              )}
            </ul>
          </div>

          <div className="panel">
            <div className="panel-heading panel-heading-row">
              <div>
                <h2>{t("overview.latestCasesTitle")}</h2>
                <p className="muted">{t("overview.latestCasesDescription")}</p>
              </div>
              <span className="tag">{t("overview.latestCasesTitle")}</span>
            </div>
            <ul className="reason-list">
              {queue?.items.length ? (
                queue.items.map((item) => (
                  <li key={item.id}>
                    <Link to={`/reviews/${item.id}`} className="inline-link">
                      <strong>
                        #{item.id} · {item.username || item.uuid || item.ip}
                      </strong>
                      <span>
                        {item.review_reason} · {item.ip} · {formatDisplayDateTime(
                          item.updated_at,
                          t("common.notAvailable"),
                          language
                        )}
                      </span>
                    </Link>
                  </li>
                ))
              ) : (
                <li>
                  <span>{t("overview.emptyLatestCases")}</span>
                </li>
              )}
            </ul>
          </div>
        </div>
      ) : null}
    </section>
  );
}
