import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { AnalysisEventItem, api, Session } from "../api/client";
import { describeScopeContext } from "../features/reviews/lib/scopeContext";
import { useI18n } from "../localization";
import { buildSearchParams } from "../shared/api/request";
import { useVisiblePolling } from "../shared/useVisiblePolling";
import { formatDisplayDateTime } from "../utils/datetime";

type DecisionFilters = {
  q: string;
  module_id: string;
  provider: string;
  verdict: string;
  decision_source: string;
  enforcement_status: string;
  page: number;
  page_size: number;
  sort: string;
};

const PAGE_SIZE_OPTIONS = [25, 50, 100];
const DECISIONS_REFRESH_MS = 15000;

const DEFAULT_FILTERS: DecisionFilters = {
  q: "",
  module_id: "",
  provider: "",
  verdict: "",
  decision_source: "",
  enforcement_status: "",
  page: 1,
  page_size: 50,
  sort: "created_desc",
};

function normalizeFilters(searchParams: URLSearchParams): DecisionFilters {
  return {
    q: searchParams.get("q") ?? "",
    module_id: searchParams.get("module_id") ?? "",
    provider: searchParams.get("provider") ?? "",
    verdict: searchParams.get("verdict") ?? "",
    decision_source: searchParams.get("decision_source") ?? "",
    enforcement_status: searchParams.get("enforcement_status") ?? "",
    page: Number(searchParams.get("page") || DEFAULT_FILTERS.page),
    page_size: Number(
      searchParams.get("page_size") || DEFAULT_FILTERS.page_size,
    ),
    sort: searchParams.get("sort") ?? DEFAULT_FILTERS.sort,
  };
}

export function DecisionsPage({ session: _session }: { session?: Session }) {
  const { t, language } = useI18n();
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState<DecisionFilters>(() =>
    normalizeFilters(searchParams),
  );
  const [data, setData] = useState<{
    items: AnalysisEventItem[];
    count: number;
    page: number;
    page_size: number;
  }>({
    items: [],
    count: 0,
    page: 1,
    page_size: DEFAULT_FILTERS.page_size,
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastUpdatedAt, setLastUpdatedAt] = useState("");

  useEffect(() => {
    const nextFilters = normalizeFilters(searchParams);
    setFilters((prev) =>
      JSON.stringify(prev) === JSON.stringify(nextFilters) ? prev : nextFilters,
    );
  }, [searchParams]);

  useEffect(() => {
    setSearchParams(new URLSearchParams(buildSearchParams(filters)), {
      replace: true,
    });
  }, [filters, setSearchParams]);

  const effectiveFilters = useMemo(() => ({ ...filters }), [filters]);
  const totalPages = Math.max(
    1,
    Math.ceil((data.count || 0) / Math.max(data.page_size || 1, 1)),
  );

  async function load() {
    try {
      const payload = await api.getAutoDecisions(effectiveFilters);
      setData(payload);
      setError("");
      setLastUpdatedAt(new Date().toISOString());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("decisions.loadFailed"));
    } finally {
      setLoading(false);
    }
  }

  useVisiblePolling(true, load, DECISIONS_REFRESH_MS, [effectiveFilters, t]);

  function updateFilter<K extends keyof DecisionFilters>(
    key: K,
    value: DecisionFilters[K],
  ) {
    setFilters((prev) => ({ ...prev, [key]: value, page: 1 }));
  }

  function formatEnforcement(item: AnalysisEventItem): string {
    const status = String(item.enforcement_status || "none").trim() || "none";
    const type = String(item.enforcement_job_type || "").trim();
    const attempts = Number(item.attempt_count || 0);
    if (status === "none") {
      return t("decisions.enforcement.none");
    }
    const parts = [t(`decisions.enforcement.status.${status}`)];
    if (type) {
      parts.push(t(`decisions.enforcement.jobType.${type}`));
    }
    if (attempts > 0) {
      parts.push(t("decisions.enforcement.attempts", { count: attempts }));
    }
    return parts.join(" · ");
  }

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <h1>{t("decisions.title")}</h1>
          <p className="page-lede">{t("decisions.description")}</p>
        </div>
        <div className="dashboard-meta">
          <div className="chip">
            {t("decisions.countSummary", {
              count: data.count,
              page: data.page,
            })}
          </div>
          <span className="muted">
            {t("decisions.lastUpdated", {
              value: formatDisplayDateTime(
                lastUpdatedAt,
                t("common.notAvailable"),
                language,
              ),
            })}
          </span>
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <h2>{t("decisions.filtersTitle")}</h2>
          <p className="muted">{t("decisions.filtersDescription")}</p>
        </div>
        <div className="filters compact-form-grid">
          <input
            placeholder={t("decisions.filters.search")}
            value={filters.q}
            onChange={(event) => updateFilter("q", event.target.value)}
          />
          <select
            value={filters.verdict}
            onChange={(event) => updateFilter("verdict", event.target.value)}
          >
            <option value="">{t("decisions.filters.anyVerdict")}</option>
            <option value="HOME">{t("data.decisions.home")}</option>
            <option value="MOBILE">{t("data.decisions.mobile")}</option>
          </select>
          <select
            value={filters.decision_source}
            onChange={(event) =>
              updateFilter("decision_source", event.target.value)
            }
          >
            <option value="">{t("decisions.filters.anySource")}</option>
            <option value="rule_engine">
              {t("decisions.sources.rule_engine")}
            </option>
            <option value="cache">{t("decisions.sources.cache")}</option>
            <option value="manual_override">
              {t("decisions.sources.manual_override")}
            </option>
          </select>
          <select
            value={filters.enforcement_status}
            onChange={(event) =>
              updateFilter("enforcement_status", event.target.value)
            }
          >
            <option value="">{t("decisions.filters.anyEnforcement")}</option>
            <option value="none">{t("decisions.enforcement.none")}</option>
            <option value="pending">
              {t("decisions.enforcement.status.pending")}
            </option>
            <option value="applied">
              {t("decisions.enforcement.status.applied")}
            </option>
            <option value="failed">
              {t("decisions.enforcement.status.failed")}
            </option>
          </select>
          <select
            value={String(filters.page_size)}
            onChange={(event) =>
              updateFilter("page_size", Number(event.target.value))
            }
          >
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {t("decisions.pagination.pageSize", { value: size })}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="panel">
        <div className="panel-heading panel-heading-row">
          <div>
            <h2>{t("decisions.listTitle")}</h2>
            <p className="muted">{t("decisions.listDescription")}</p>
          </div>
          <span className="tag">
            {t("decisions.pagination.page", {
              page: data.page,
              total: totalPages,
            })}
          </span>
        </div>
        <div className="record-list">
          {loading ? (
            <div className="provider-empty">
              <span>{t("common.loading")}</span>
            </div>
          ) : null}
          {!loading && data.items.length === 0 ? (
            <div className="provider-empty">
              <span>{t("decisions.empty")}</span>
            </div>
          ) : null}
          {!loading
            ? data.items.map((item) => {
                const scopeContext = describeScopeContext(
                  t,
                  item.target_scope_type,
                  Boolean(item.shared_account_suspected),
                );
                const contextDisplay =
                  scopeContext.scopeType === "ip_device"
                    ? item.device_display || t("common.notAvailable")
                    : scopeContext.contextValue;
                return (
                  <div className="record-item" key={String(item.id)}>
                    <div className="record-main">
                      <span className="record-title">
                        {item.target_ip || item.ip} · {contextDisplay}
                      </span>
                      <span className="tag">
                        {item.verdict} / {item.confidence_band}
                      </span>
                    </div>
                    <div className="record-meta">
                      <span>
                        {t("decisions.meta.module", {
                          value: String(
                            item.module_name || item.module_id || "—",
                          ),
                        })}
                      </span>
                      <span>
                        {t("decisions.meta.inbound", {
                          value: String(item.inbound_tag || item.tag || "—"),
                        })}
                      </span>
                      <span>
                        {t("decisions.meta.provider", {
                          value: String(item.isp || "—"),
                        })}
                      </span>
                      <span>
                        {t("decisions.meta.source", {
                          value: t(
                            `decisions.sources.${String(item.decision_source || "rule_engine")}`,
                          ),
                        })}
                      </span>
                      <span>
                        {formatDisplayDateTime(
                          item.created_at,
                          t("common.notAvailable"),
                          language,
                        )}
                      </span>
                    </div>
                    <div className="record-meta">
                      <span>
                        {t("decisions.meta.scope", {
                          value: scopeContext.scopeMeta,
                        })}
                      </span>
                      <span>
                        {t("decisions.meta.enforcement", {
                          value: formatEnforcement(item),
                        })}
                      </span>
                    </div>
                    {item.last_error ? (
                      <div className="error-box">{item.last_error}</div>
                    ) : null}
                  </div>
                );
              })
            : null}
        </div>
        <div className="record-actions">
          <button
            className="ghost"
            disabled={filters.page <= 1}
            onClick={() =>
              setFilters((prev) => ({
                ...prev,
                page: Math.max(prev.page - 1, 1),
              }))
            }
          >
            {t("decisions.pagination.previous")}
          </button>
          <button
            className="ghost"
            disabled={filters.page >= totalPages}
            onClick={() =>
              setFilters((prev) => ({
                ...prev,
                page: Math.min(prev.page + 1, totalPages),
              }))
            }
          >
            {t("decisions.pagination.next")}
          </button>
        </div>
      </div>
    </section>
  );
}
