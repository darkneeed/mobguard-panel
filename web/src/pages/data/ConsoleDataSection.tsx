import { ConsoleListResponse } from "../../api/client";
import { useVisibleItems } from "../../shared/useVisibleItems";

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
  const {
    visibleItems: visibleConsoleItems,
    hasMore: hasMoreConsoleItems,
    loadMoreRef: loadMoreConsoleRef,
  } = useVisibleItems(items, { initialCount: 20, step: 20 });

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

      <div 
        className="panel console-panel" 
        style={{ 
          background: "#080b11", 
          borderRadius: "12px", 
          border: "1px solid var(--line)", 
          padding: 0, 
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          boxShadow: "var(--shadow)"
        }}
      >
        {/* Terminal Header */}
        <div style={{
          background: "rgba(15, 23, 42, 0.4)",
          padding: "0.6rem 1rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid var(--line)"
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
            <span style={{ width: "11px", height: "11px", borderRadius: "50%", background: "#ef4444", display: "inline-block" }}></span>
            <span style={{ width: "11px", height: "11px", borderRadius: "50%", background: "#eab308", display: "inline-block" }}></span>
            <span style={{ width: "11px", height: "11px", borderRadius: "50%", background: "#22c55e", display: "inline-block" }}></span>
            <span style={{ color: "var(--muted)", fontSize: "0.78rem", fontFamily: "var(--font-mono, monospace)", marginLeft: "0.5rem", fontWeight: 500 }}>
              operator@mobguard-shell:~
            </span>
          </div>
          <span style={{ color: "var(--muted)", fontSize: "0.75rem", fontFamily: "var(--font-mono, monospace)" }}>
            {t("data.console.pagination.page", {
              page: currentPage,
              total: totalPages,
            })}
          </span>
        </div>

        {/* Console logs body */}
        <div 
          className="console-stream" 
          style={{ 
            padding: "1rem", 
            flex: 1, 
            display: "flex", 
            flexDirection: "column", 
            gap: "0.35rem", 
            overflowY: "auto", 
            maxHeight: "35rem",
            minHeight: "28rem"
          }}
        >
          {items.length === 0 ? (
            <div className="provider-empty" style={{ background: "transparent", border: 0 }}>
              <span style={{ fontFamily: "var(--font-mono, monospace)", color: "var(--muted)" }}>
                {t("data.console.empty")}
              </span>
            </div>
          ) : null}
          {visibleConsoleItems.map((item) => (
            <div 
              key={item.id} 
              className={`console-line level-${item.level}`}
              style={{
                fontFamily: "var(--font-mono, 'JetBrains Mono', Consolas, monospace)",
                fontSize: "0.82rem",
                lineHeight: "1.5",
                padding: "0.35rem 0.5rem",
                borderRadius: "6px",
                borderBottom: "1px solid rgba(255, 255, 255, 0.015)",
                display: "flex",
                flexDirection: "column",
                gap: "0.25rem",
                transition: "background 0.15s ease",
                backgroundColor: "rgba(255, 255, 255, 0.005)"
              }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.03)" }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.005)" }}
            >
              {/* Header / Meta Row */}
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "0.5rem", color: "var(--muted)" }}>
                <span style={{ color: "#475569" }}>
                  [{item.timestamp ? item.timestamp.split("T").join(" ").split("Z").join("") : "N/A"}]
                </span>
                <span style={{ 
                  color: item.level === "error" ? "var(--danger)" : item.level === "warn" ? "var(--warning)" : "var(--accent)",
                  fontWeight: 600
                }}>
                  [{item.level.toUpperCase()}]
                </span>
                {item.module_id && (
                  <span style={{ color: "var(--accent-strong)" }}>
                    [{item.module_name || item.module_id}]
                  </span>
                )}
                {item.service_name && (
                  <span style={{ color: "var(--accent)" }}>
                    ({item.service_name})
                  </span>
                )}
                {item.logger_name && (
                  <span style={{ color: "#475569", fontSize: "0.78rem" }}>
                    {item.logger_name}
                  </span>
                )}
              </div>

              {/* Message Row */}
              <div style={{ color: "var(--ink)", paddingLeft: "0.5rem", wordBreak: "break-all", whiteSpace: "pre-wrap" }}>
                {item.message}
              </div>

              {/* Collapsible Details Row */}
              {(item.payload || item.meta) && (
                <div style={{ paddingLeft: "0.5rem", marginTop: "0.15rem" }}>
                  <details style={{ cursor: "pointer" }}>
                    <summary style={{ fontSize: "0.75rem", color: "var(--muted)", outline: "none", userSelect: "none" }}>
                      [PAYLOAD / METADATA]
                    </summary>
                    <pre style={{
                      margin: "0.35rem 0 0 0",
                      padding: "0.65rem 0.85rem",
                      background: "rgba(0, 0, 0, 0.4)",
                      border: "1px solid var(--line)",
                      borderRadius: "8px",
                      fontSize: "0.78rem",
                      color: "var(--success)",
                      maxHeight: "20rem",
                      overflow: "auto",
                      fontFamily: "var(--font-mono, monospace)"
                    }}>
                      {JSON.stringify({ payload: item.payload, meta: item.meta }, null, 2)}
                    </pre>
                  </details>
                </div>
              )}
            </div>
          ))}
          {hasMoreConsoleItems ? (
            <div className="provider-empty muted" ref={loadMoreConsoleRef} style={{ background: "transparent", border: 0 }}>
              <span style={{ fontFamily: "var(--font-mono, monospace)", color: "var(--muted)" }}>
                {t("common.loading")}
              </span>
            </div>
          ) : null}
        </div>

        {/* Terminal Footer / Actions */}
        <div style={{
          background: "rgba(15, 23, 42, 0.4)",
          padding: "0.6rem 1rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderTop: "1px solid var(--line)"
        }}>
          <div style={{ fontSize: "0.75rem", color: "var(--muted)", fontFamily: "var(--font-mono, monospace)" }}>
            {t("data.console.count", { count: totalCount })}
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              className="ghost small-button"
              disabled={currentPage <= 1}
              style={{
                background: "transparent",
                border: "1px solid var(--line)",
                color: currentPage <= 1 ? "var(--muted)" : "var(--ink)",
                padding: "0.35rem 0.75rem",
                borderRadius: "6px",
                fontSize: "0.75rem",
                fontFamily: "var(--font-mono, monospace)",
                cursor: currentPage <= 1 ? "not-allowed" : "pointer"
              }}
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
              className="ghost small-button"
              disabled={currentPage >= totalPages}
              style={{
                background: "transparent",
                border: "1px solid var(--line)",
                color: currentPage >= totalPages ? "var(--muted)" : "var(--ink)",
                padding: "0.35rem 0.75rem",
                borderRadius: "6px",
                fontSize: "0.75rem",
                fontFamily: "var(--font-mono, monospace)",
                cursor: currentPage >= totalPages ? "not-allowed" : "pointer"
              }}
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
    </div>
  );
}
