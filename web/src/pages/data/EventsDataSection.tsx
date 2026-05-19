import { Link } from "react-router-dom";
import { AnalysisEventListResponse } from "../../api/client";
import { describeScopeContext } from "../../features/reviews/lib/scopeContext";
import type { Language } from "../../localization/types";
import { useVisibleItems } from "../../shared/useVisibleItems";
import { formatDisplayDateTime } from "../../utils/datetime";

type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

type EventFilters = {
  q: string;
  ip: string;
  device_id: string;
  module_id: string;
  tag: string;
  provider: string;
  asn: string;
  verdict: string;
  confidence_band: string;
  has_review_case: string;
  page: number;
  page_size: number;
};

type Props = {
  t: TranslateFn;
  language: Language;
  events: AnalysisEventListResponse | null;
  filters: EventFilters;
  setFilters: (updater: (prev: EventFilters) => EventFilters) => void;
};

export function EventsDataSection({ t, language, events, filters, setFilters }: Props) {
  const items = events?.items || [];
  const currentPage = events?.page ?? filters.page;
  const pageSize = events?.page_size ?? filters.page_size;
  const totalCount = events?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / Math.max(pageSize, 1)));
  const {
    visibleItems: visibleEventItems,
    hasMore: hasMoreEvents,
    loadMoreRef: loadMoreEventsRef,
  } = useVisibleItems(items, { initialCount: 12, step: 12 });

  function updateFilters(updater: (prev: EventFilters) => EventFilters) {
    setFilters(updater);
  }

  function updateFilter<K extends keyof EventFilters>(key: K, value: EventFilters[K]) {
    updateFilters((prev) => ({ ...prev, [key]: value, page: 1 }));
  }

  function hasData(value: unknown): boolean {
    if (value === null || value === undefined) return false;
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === "object") return Object.keys(value as Record<string, unknown>).length > 0;
    return true;
  }

  function renderJsonBlock(label: string, value: unknown) {
    if (!hasData(value)) {
      return null;
    }
    return (
      <details className="record-json" key={label}>
        <summary>{label}</summary>
        <pre>{JSON.stringify(value, null, 2)}</pre>
      </details>
    );
  }

  return (
    <div className="detail-grid">
      <div className="panel">
        <div className="panel-heading">
          <h2>{t("data.events.filtersTitle")}</h2>
          <p className="muted">{t("data.events.description")}</p>
        </div>
        <div className="filters compact-form-grid">
          <input
            placeholder={t("data.events.filters.search")}
            value={filters.q}
            onChange={(event) => updateFilter("q", event.target.value)}
          />
          <input
            placeholder={t("data.events.filters.ip")}
            value={filters.ip}
            onChange={(event) => updateFilter("ip", event.target.value)}
          />
          <input
            placeholder={t("data.events.filters.deviceId")}
            value={filters.device_id}
            onChange={(event) => updateFilter("device_id", event.target.value)}
          />
          <input
            placeholder={t("data.events.filters.moduleId")}
            value={filters.module_id}
            onChange={(event) => updateFilter("module_id", event.target.value)}
          />
          <input
            placeholder={t("data.events.filters.inbound")}
            value={filters.tag}
            onChange={(event) => updateFilter("tag", event.target.value)}
          />
          <input
            placeholder={t("data.events.filters.provider")}
            value={filters.provider}
            onChange={(event) => updateFilter("provider", event.target.value)}
          />
          <input
            placeholder={t("data.events.filters.asn")}
            value={filters.asn}
            onChange={(event) => updateFilter("asn", event.target.value)}
          />
          <select
            value={filters.verdict}
            onChange={(event) => updateFilter("verdict", event.target.value)}
          >
            <option value="">{t("data.events.filters.anyVerdict")}</option>
            <option value="HOME">{t("data.decisions.home")}</option>
            <option value="MOBILE">{t("data.decisions.mobile")}</option>
            <option value="UNSURE">{t("reviewQueue.filters.confidenceUnsure")}</option>
          </select>
          <select
            value={filters.confidence_band}
            onChange={(event) => updateFilter("confidence_band", event.target.value)}
          >
            <option value="">{t("data.events.filters.anyConfidence")}</option>
            <option value="HIGH_HOME">{t("reviewQueue.filters.confidenceHighHome")}</option>
            <option value="PROBABLE_HOME">{t("reviewQueue.filters.confidenceProbableHome")}</option>
            <option value="UNSURE">{t("reviewQueue.filters.confidenceUnsure")}</option>
            <option value="HIGH_MOBILE">{t("data.events.filters.highMobile")}</option>
          </select>
          <select
            value={filters.has_review_case}
            onChange={(event) => updateFilter("has_review_case", event.target.value)}
          >
            <option value="">{t("data.events.filters.anyCase")}</option>
            <option value="true">{t("data.events.filters.withCase")}</option>
            <option value="false">{t("data.events.filters.withoutCase")}</option>
          </select>
          <select
            value={String(pageSize)}
            onChange={(event) => updateFilter("page_size", Number(event.target.value))}
          >
            <option value="25">{t("data.events.pagination.pageSizeOption", { value: 25 })}</option>
            <option value="50">{t("data.events.pagination.pageSizeOption", { value: 50 })}</option>
            <option value="100">{t("data.events.pagination.pageSizeOption", { value: 100 })}</option>
          </select>
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading panel-heading-row">
          <div>
            <h2>{t("data.events.title")}</h2>
            <p className="muted">{t("data.events.count", { count: totalCount })}</p>
          </div>
          <span className="tag">{t("data.events.pagination.page", { page: currentPage, total: totalPages })}</span>
        </div>
        <div className="record-list">
          {items.length === 0 ? (
            <div className="provider-empty">
              <span>{t("data.events.empty")}</span>
            </div>
          ) : null}
          {visibleEventItems.map((item) => (
            (() => {
              const scopeContext = describeScopeContext(
                t,
                item.target_scope_type,
                Boolean(item.shared_account_suspected)
              );
              const contextDisplay = scopeContext.scopeType === "ip_device"
                ? item.device_display || t("common.notAvailable")
                : scopeContext.contextValue;
              return (
                <div className="record-item" key={String(item.id)}>
                  <div className="record-main">
                    <span className="record-title">
                      {item.target_ip || item.ip} · {contextDisplay}
                    </span>
                    <span className="tag">{item.verdict} / {item.confidence_band}</span>
                  </div>
                  <div className="record-meta">
                    <span>{t("data.events.meta.module", { value: String(item.module_name || item.module_id || "—") })}</span>
                    <span>{t("data.events.meta.inbound", { value: String(item.inbound_tag || item.tag || "—") })}</span>
                    <span>{t("data.events.meta.provider", { value: String(item.isp || "—") })}</span>
                    <span>{t("data.events.meta.asn", { value: String(item.asn ?? "—") })}</span>
                    <span>{formatDisplayDateTime(item.created_at, t("common.notAvailable"), language)}</span>
                  </div>
                  <div className="record-meta">
                    <span>{t("data.events.meta.scope", { value: scopeContext.scopeMeta })}</span>
                    <span>
                      {item.review_case_id ? (
                        <Link to={`/reviews/${item.review_case_id}`}>
                          {t("data.events.meta.case", { value: `#${item.review_case_id}` })}
                        </Link>
                      ) : (
                        t("data.events.meta.case", { value: t("data.events.noCase") })
                      )}
                    </span>
                    <span>{String(item.city || item.country || t("common.notAvailable"))}</span>
                  </div>
                  <div className="record-json-stack">
                    {renderJsonBlock(t("data.events.details.providerEvidence"), item.provider_evidence)}
                    {renderJsonBlock(t("data.events.details.reasons"), item.reasons)}
                    {renderJsonBlock(t("data.events.details.signalFlags"), item.signal_flags)}
                    {renderJsonBlock(t("data.events.details.rawBundle"), item.bundle)}
                  </div>
                </div>
              );
            })()
          ))}
          {hasMoreEvents ? (
            <div className="provider-empty muted" ref={loadMoreEventsRef}>
              <span>{t("common.loading")}</span>
            </div>
          ) : null}
        </div>
        <div className="record-actions">
          <button
            className="ghost"
            disabled={currentPage <= 1}
            onClick={() => updateFilters((prev) => ({ ...prev, page: Math.max(prev.page - 1, 1) }))}
          >
            {t("data.events.pagination.previous")}
          </button>
          <button
            className="ghost"
            disabled={currentPage >= totalPages}
            onClick={() => updateFilters((prev) => ({ ...prev, page: Math.min(prev.page + 1, totalPages) }))}
          >
            {t("data.events.pagination.next")}
          </button>
        </div>
      </div>
    </div>
  );
}
