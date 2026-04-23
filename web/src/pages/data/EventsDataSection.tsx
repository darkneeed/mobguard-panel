import { Link } from "react-router-dom";
import { AnalysisEventListResponse } from "../../api/client";
import type { Language } from "../../localization/types";
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
            onChange={(event) => setFilters((prev) => ({ ...prev, q: event.target.value }))}
          />
          <input
            placeholder={t("data.events.filters.ip")}
            value={filters.ip}
            onChange={(event) => setFilters((prev) => ({ ...prev, ip: event.target.value }))}
          />
          <input
            placeholder={t("data.events.filters.deviceId")}
            value={filters.device_id}
            onChange={(event) => setFilters((prev) => ({ ...prev, device_id: event.target.value }))}
          />
          <input
            placeholder={t("data.events.filters.moduleId")}
            value={filters.module_id}
            onChange={(event) => setFilters((prev) => ({ ...prev, module_id: event.target.value }))}
          />
          <input
            placeholder={t("data.events.filters.inbound")}
            value={filters.tag}
            onChange={(event) => setFilters((prev) => ({ ...prev, tag: event.target.value }))}
          />
          <input
            placeholder={t("data.events.filters.provider")}
            value={filters.provider}
            onChange={(event) => setFilters((prev) => ({ ...prev, provider: event.target.value }))}
          />
          <input
            placeholder={t("data.events.filters.asn")}
            value={filters.asn}
            onChange={(event) => setFilters((prev) => ({ ...prev, asn: event.target.value }))}
          />
          <select
            value={filters.verdict}
            onChange={(event) => setFilters((prev) => ({ ...prev, verdict: event.target.value }))}
          >
            <option value="">{t("data.events.filters.anyVerdict")}</option>
            <option value="HOME">{t("data.decisions.home")}</option>
            <option value="MOBILE">{t("data.decisions.mobile")}</option>
            <option value="UNSURE">{t("reviewQueue.filters.confidenceUnsure")}</option>
          </select>
          <select
            value={filters.confidence_band}
            onChange={(event) => setFilters((prev) => ({ ...prev, confidence_band: event.target.value }))}
          >
            <option value="">{t("data.events.filters.anyConfidence")}</option>
            <option value="HIGH_HOME">{t("reviewQueue.filters.confidenceHighHome")}</option>
            <option value="PROBABLE_HOME">{t("reviewQueue.filters.confidenceProbableHome")}</option>
            <option value="UNSURE">{t("reviewQueue.filters.confidenceUnsure")}</option>
            <option value="HIGH_MOBILE">{t("data.events.filters.highMobile")}</option>
          </select>
          <select
            value={filters.has_review_case}
            onChange={(event) => setFilters((prev) => ({ ...prev, has_review_case: event.target.value }))}
          >
            <option value="">{t("data.events.filters.anyCase")}</option>
            <option value="true">{t("data.events.filters.withCase")}</option>
            <option value="false">{t("data.events.filters.withoutCase")}</option>
          </select>
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading panel-heading-row">
          <div>
            <h2>{t("data.events.title")}</h2>
            <p className="muted">{t("data.events.count", { count: events?.count ?? 0 })}</p>
          </div>
        </div>
        <div className="record-list">
          {items.length === 0 ? (
            <div className="provider-empty">
              <span>{t("data.events.empty")}</span>
            </div>
          ) : null}
          {items.map((item) => (
            <div className="record-item" key={String(item.id)}>
              <div className="record-main">
                <span className="record-title">
                  {item.target_ip || item.ip} · {item.device_display || t("data.events.ipOnly")}
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
                <span>{t("data.events.meta.scope", { value: String(item.target_scope_type || "ip_only") })}</span>
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
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
