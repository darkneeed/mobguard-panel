import { ConsoleListResponse } from "../../api/client";

type TranslateFn = (
  key: string,
  params?: Record<string, string | number>,
) => string;

type ConsoleFilters = {
  q: string;
  source: string;
  level: string;
  module_id: string;
  page: number;
  page_size: number;
};

type Props = {
  t: TranslateFn;
  consoleData: ConsoleListResponse | null;
  filters: ConsoleFilters;
  setFilters: (updater: (prev: ConsoleFilters) => ConsoleFilters) => void;
};

export function ConsoleDataSection({
  t,
  consoleData,
  filters,
  setFilters,
}: Props) {
  const items = consoleData?.items || [];
  const currentPage = consoleData?.page ?? filters.page;
  const pageSize = consoleData?.page_size ?? filters.page_size;
  const totalCount = consoleData?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / Math.max(pageSize, 1)));
  const sourceCounts = consoleData?.source_counts || {};

  function updateFilter<K extends keyof ConsoleFilters>(
    key: K,
    value: ConsoleFilters[K],
  ) {
    setFilters((prev) => ({ ...prev, [key]: value, page: 1 }));
  }

  function renderPayload(
    label: string,
    payload: Record<string, unknown> | null | undefined,
  ) {
    if (!payload || Object.keys(payload).length === 0) {
      return null;
    }
    return (
      <details className="record-json" key={label}>
        <summary>{label}</summary>
        <pre>{JSON.stringify(payload, null, 2)}</pre>
      </details>
    );
  }

  return (
    <div className="detail-grid">
      <div className="panel">
        <div className="panel-heading">
          <h2>{t("data.console.filtersTitle")}</h2>
          <p className="muted">{t("data.console.description")}</p>
        </div>
        <div className="filters compact-form-grid">
          <input
            placeholder={t("data.console.filters.search")}
            value={filters.q}
            onChange={(event) => updateFilter("q", event.target.value)}
          />
          <select
            value={filters.source}
            onChange={(event) => updateFilter("source", event.target.value)}
          >
            <option value="">{t("data.console.filters.anySource")}</option>
            <option value="system">{t("data.console.sources.system")}</option>
            <option value="module_event">
              {t("data.console.sources.module_event")}
            </option>
            <option value="module_heartbeat">
              {t("data.console.sources.module_heartbeat")}
            </option>
          </select>
          <select
            value={filters.level}
            onChange={(event) => updateFilter("level", event.target.value)}
          >
            <option value="">{t("data.console.filters.anyLevel")}</option>
            <option value="info">{t("data.console.levels.info")}</option>
            <option value="warn">{t("data.console.levels.warn")}</option>
            <option value="error">{t("data.console.levels.error")}</option>
          </select>
          <input
            placeholder={t("data.console.filters.moduleId")}
            value={filters.module_id}
            onChange={(event) => updateFilter("module_id", event.target.value)}
          />
          <select
            value={String(pageSize)}
            onChange={(event) =>
              updateFilter("page_size", Number(event.target.value))
            }
          >
            <option value="50">
              {t("data.console.pagination.pageSizeOption", { value: 50 })}
            </option>
            <option value="100">
              {t("data.console.pagination.pageSizeOption", { value: 100 })}
            </option>
            <option value="200">
              {t("data.console.pagination.pageSizeOption", { value: 200 })}
            </option>
          </select>
        </div>
        <div className="record-meta">
          <span className="chip">
            {t("data.console.sourceCount.system", {
              count: sourceCounts.system ?? 0,
            })}
          </span>
          <span className="chip">
            {t("data.console.sourceCount.moduleEvents", {
              count: sourceCounts.module_event ?? 0,
            })}
          </span>
          <span className="chip">
            {t("data.console.sourceCount.moduleHeartbeats", {
              count: sourceCounts.module_heartbeat ?? 0,
            })}
          </span>
        </div>
      </div>

      <div className="panel console-panel">
        <div className="panel-heading panel-heading-row">
          <div>
            <h2>{t("data.console.title")}</h2>
            <p className="muted">
              {t("data.console.count", { count: totalCount })}
            </p>
          </div>
          <span className="tag">
            {t("data.console.pagination.page", {
              page: currentPage,
              total: totalPages,
            })}
          </span>
        </div>
        <div className="console-stream">
          {items.length === 0 ? (
            <div className="provider-empty">
              <span>{t("data.console.empty")}</span>
            </div>
          ) : null}
          {items.map((item) => (
            <article
              className={`console-entry console-entry-${item.level}`}
              key={item.id}
            >
              <div className="console-entry-head">
                <span className="console-entry-time">
                  {item.timestamp || t("common.notAvailable")}
                </span>
                <span className="tag">
                  {t(`data.console.sources.${item.source}`)}
                </span>
                <span className={`tag console-level-${item.level}`}>
                  {t(`data.console.levels.${item.level}`)}
                </span>
                {item.module_id ? (
                  <span className="tag">{item.module_id}</span>
                ) : null}
                {item.service_name ? (
                  <span className="tag">{item.service_name}</span>
                ) : null}
              </div>
              <div className="console-entry-message">{item.message}</div>
              <div className="console-entry-meta">
                {item.module_name ? (
                  <span>
                    {t("data.console.meta.moduleName", {
                      value: item.module_name,
                    })}
                  </span>
                ) : null}
                {item.logger_name ? (
                  <span>
                    {t("data.console.meta.logger", { value: item.logger_name })}
                  </span>
                ) : null}
                {item.event_uid ? (
                  <span>
                    {t("data.console.meta.eventUid", { value: item.event_uid })}
                  </span>
                ) : null}
              </div>
              <div className="record-json-stack">
                {renderPayload(
                  t("data.console.payload"),
                  item.payload || undefined,
                )}
                {renderPayload(
                  t("data.console.metaPayload"),
                  item.meta || undefined,
                )}
              </div>
            </article>
          ))}
        </div>
        <div className="record-actions">
          <button
            className="ghost"
            disabled={currentPage <= 1}
            onClick={() =>
              setFilters((prev) => ({
                ...prev,
                page: Math.max(prev.page - 1, 1),
              }))
            }
          >
            {t("data.console.pagination.previous")}
          </button>
          <button
            className="ghost"
            disabled={currentPage >= totalPages}
            onClick={() =>
              setFilters((prev) => ({
                ...prev,
                page: Math.min(prev.page + 1, totalPages),
              }))
            }
          >
            {t("data.console.pagination.next")}
          </button>
        </div>
      </div>
    </div>
  );
}
