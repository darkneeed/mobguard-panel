import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Shield } from "lucide-react";

import { AnalysisEventItem, api, Session, AutomationStatus } from "../api/client";
import { describeScopeContext } from "../features/reviews/lib/scopeContext";
import { useI18n } from "../localization";
import {
  automationGuardrailLabels,
  automationModeLabel,
  automationModeReasonLabels,
} from "../shared/automationStatus";
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

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];
const DECISIONS_REFRESH_MS = 15000;
const INITIAL_VISIBLE_CARDS = 12;
const VISIBLE_CARDS_STEP = 12;

const DEFAULT_FILTERS: DecisionFilters = {
  q: "",
  module_id: "",
  provider: "",
  verdict: "",
  decision_source: "",
  enforcement_status: "",
  page: 1,
  page_size: 20,
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
  const [visibleCardsCount, setVisibleCardsCount] = useState(filters.page_size);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const [automationStatus, setAutomationStatus] = useState<AutomationStatus | null>(null);

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
  const visibleItems = useMemo(
    () => data.items.slice(0, visibleCardsCount),
    [data.items, visibleCardsCount],
  );

  async function load() {
    try {
      const [payload, enforcementPayload] = await Promise.all([
        api.getAutoDecisions({
          ...effectiveFilters,
          compact: true,
        }),
        api.getEnforcementSettings(),
      ]);
      setData(payload);
      setAutomationStatus(enforcementPayload.automation_status ?? null);
      setError("");
      setLastUpdatedAt(new Date().toISOString());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("decisions.loadFailed"));
    } finally {
      setLoading(false);
    }
  }

  useVisiblePolling(true, load, DECISIONS_REFRESH_MS, [effectiveFilters, t]);

  useEffect(() => {
    setVisibleCardsCount(filters.page_size);
  }, [data.items, filters.page_size]);

  useEffect(() => {
    if (loading) {
      return;
    }
    if (visibleCardsCount >= data.items.length) {
      return;
    }
    const node = loadMoreRef.current;
    if (!node) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisibleCardsCount((prev) =>
            Math.min(prev + VISIBLE_CARDS_STEP, data.items.length),
          );
        }
      },
      { rootMargin: "240px 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [data.items.length, loading, visibleCardsCount]);

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

  function userIdentifier(item: AnalysisEventItem): string {
    return String(
      item.uuid || item.system_id || item.telegram_id || item.username || "",
    ).trim();
  }

  function decisionHighlights(item: AnalysisEventItem): string[] {
    const highlights: string[] = [];
    const reasons = Array.isArray(item.reasons) ? item.reasons : [];
    for (const reason of reasons) {
      if (!reason || typeof reason !== "object") continue;
      const label = String(
        (reason as Record<string, unknown>).label ||
          (reason as Record<string, unknown>).code ||
          "",
      ).trim();
      if (label) {
        highlights.push(label);
      }
      if (highlights.length >= 3) break;
    }
    if (highlights.length === 0 && Array.isArray(item.hard_flags)) {
      return item.hard_flags
        .map((flag) => String(flag || "").trim())
        .filter(Boolean)
        .slice(0, 3);
    }
    return highlights;
  }

  const automationModeReasons = automationModeReasonLabels(t, automationStatus);
  const automationGuardrails = automationGuardrailLabels(t, automationStatus);
  const automationMode = automationModeLabel(t, automationStatus);
  const automationModeBadgeClass =
    automationStatus?.mode === "enforce"
      ? "status-resolved"
      : automationStatus?.mode === "warning_only"
        ? "severity-high"
        : "review-only";

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <h1>{t("decisions.title")}</h1>
          <p className="page-lede">{t("decisions.description")}</p>
        </div>
        <div className="dashboard-meta" style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
          <div className="chip">
            {t("decisions.countSummary", {
              count: data.count,
              page: data.page,
            })}
          </div>
          <span className="muted" style={{ fontSize: "0.85rem" }}>
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

      {automationStatus && (
        <div className="panel" style={{ marginBottom: "1.5rem" }}>
          <div className="panel-heading">
            <h2>Автоматизация решений</h2>
            <p className="muted">
              Текущий режим работы и критерии автоматического применения мер к пользователям.
            </p>
          </div>
          
          <div className={`automation-banner ${automationModeBadgeClass}`}>
            <div className="automation-banner-icon">
              <Shield size={24} />
            </div>
            <div className="automation-banner-content">
              <h3 className="automation-banner-title">
                Режим: {automationMode}
              </h3>
              <p className="automation-banner-desc">
                {automationStatus.mode === "enforce"
                  ? "Все ограничения применяются на Remnawave в реальном времени автоматически."
                  : automationStatus.mode === "warning_only"
                    ? "Режим симуляции (Dry Run). Решения записываются в журнал решений, но не применяются на Remnawave."
                    : "Автоматическое принятие решений отключено. Все инциденты направляются на ручную модерацию."}
              </p>
            </div>
          </div>

          <div className="automation-info-grid">
            <div className="automation-info-card">
              <h4>Причины переключения режима</h4>
              {automationModeReasons.length ? (
                <div className="automation-tag-list">
                  {automationModeReasons.map((reason) => (
                    <div className="automation-tag-item warning" key={reason}>
                      <span>⚠️</span>
                      <span>{reason}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
                  Активных условий переключения режима нет (штатный режим).
                </p>
              )}
            </div>

            <div className="automation-info-card">
              <h4>Активные предохранители (Guardrails)</h4>
              {automationGuardrails.length ? (
                <div className="automation-tag-list">
                  {automationGuardrails.map((guardrail) => (
                    <div className="automation-tag-item danger" key={guardrail}>
                      <span>🛡️</span>
                      <span>{guardrail}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
                  Предохранители не активны (система работает без ограничений скорости блокировок).
                </p>
              )}
            </div>
          </div>

          <div className="action-row" style={{ marginTop: "1.5rem", borderTop: "1px solid var(--line)", paddingTop: "1rem" }}>
            <Link className="button-link" to="/rules/general">
              Настроить правила и лимиты
            </Link>
          </div>
        </div>
      )}

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
        <div className="panel-heading panel-heading-row" style={{ borderBottom: "1px solid var(--line)", paddingBottom: "1rem", marginBottom: "1.5rem" }}>
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

        {!loading && data.items.length > 0 ? (
          <div className="queue-grid review-queue-grid" style={{ marginBottom: "1.5rem" }}>
            {visibleItems.map((item) => {
              const scopeContext = describeScopeContext(
                t,
                item.target_scope_type,
                Boolean(item.shared_account_suspected),
              );
              const contextDisplay =
                scopeContext.scopeType === "ip_device"
                  ? item.device_display || t("common.notAvailable")
                  : scopeContext.contextValue;
              const identifier = userIdentifier(item);
              const highlights = decisionHighlights(item);
              const targetTo = identifier
                ? `/data/users?identifier=${encodeURIComponent(identifier)}`
                : "";
              const isVerdictHome = item.verdict === "HOME";
              const isVerdictMobile = item.verdict === "MOBILE";
              const verdictClass = isVerdictHome ? "punitive" : isVerdictMobile ? "status-resolved" : "severity-low";

              return (
                <article
                  key={String(item.id)}
                  className="queue-card"
                  style={{ display: "flex", flexDirection: "column", gap: "0.85rem", padding: "1.25rem", borderRadius: "14px", border: "1px solid var(--line)" }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem" }}>
                    <div>
                      <strong style={{ fontSize: "1.1rem", color: "var(--ink)", fontFamily: "var(--font-display)", wordBreak: "break-all" }}>
                        {item.target_ip || item.ip}
                      </strong>
                      <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "0.2rem" }}>
                        {scopeContext.queueScopeLabel || scopeContext.scopeMeta} · {contextDisplay}
                      </div>
                    </div>
                    <span className={`status-badge ${verdictClass}`} style={{ fontWeight: 700, padding: "0.2rem 0.6rem", fontSize: "0.75rem", borderRadius: "6px", whiteSpace: "nowrap" }}>
                      {item.verdict}
                    </span>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem", fontSize: "0.8rem" }}>
                    <div>
                      <span style={{ color: "var(--muted)", display: "block", fontSize: "0.7rem", textTransform: "uppercase", fontWeight: 600 }}>Пользователь</span>
                      {targetTo ? (
                        <Link to={targetTo} style={{ color: "var(--accent)", textDecoration: "underline", fontWeight: 600 }}>
                          {identifier || "—"}
                        </Link>
                      ) : (
                        <strong style={{ color: "var(--ink)" }}>{identifier || "—"}</strong>
                      )}
                    </div>
                    <div>
                      <span style={{ color: "var(--muted)", display: "block", fontSize: "0.7rem", textTransform: "uppercase", fontWeight: 600 }}>Модуль / Вход</span>
                      <strong style={{ color: "var(--ink)" }}>
                        {item.module_name || item.module_id || "—"}
                        <span style={{ color: "var(--muted)", fontWeight: "normal" }}>
                          {item.inbound_tag || item.tag ? ` (${item.inbound_tag || item.tag})` : ""}
                        </span>
                      </strong>
                    </div>
                    <div>
                      <span style={{ color: "var(--muted)", display: "block", fontSize: "0.7rem", textTransform: "uppercase", fontWeight: 600 }}>Источник вердикта</span>
                      <span style={{ color: "var(--ink)", fontWeight: 500 }}>
                        {t(`decisions.sources.${String(item.decision_source || "rule_engine")}`)}
                      </span>
                    </div>
                    <div>
                      <span style={{ color: "var(--muted)", display: "block", fontSize: "0.7rem", textTransform: "uppercase", fontWeight: 600 }}>Показатели</span>
                      <span style={{ color: "var(--ink)", fontWeight: 500 }}>
                        Балл: {item.score} | HWID: {item.hwid_device_count_exact ?? "—"}/{item.hwid_device_limit ?? "—"}
                      </span>
                    </div>
                  </div>

                  <div style={{ background: "rgba(255, 255, 255, 0.02)", border: "1px solid var(--line)", borderRadius: "8px", padding: "0.5rem 0.75rem", fontSize: "0.8rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ color: "var(--muted)", fontSize: "0.75rem" }}>Провайдер:</span>
                    <strong style={{ color: "var(--ink)", maxWidth: "70%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: "0.8rem" }} title={item.isp || ""}>
                      {item.isp || "—"}
                    </strong>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.75rem", borderTop: "1px solid var(--line)", paddingTop: "0.6rem", marginTop: "auto" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--muted)" }}>Статус исполнения:</span>
                      <strong style={{ color: item.enforcement_status === "failed" ? "var(--danger)" : item.enforcement_status === "applied" ? "var(--success)" : "var(--ink)" }}>
                        {formatEnforcement(item)}
                      </strong>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", color: "var(--muted)", fontSize: "0.7rem" }}>
                      <span>Создано:</span>
                      <span>{formatDisplayDateTime(item.created_at, "—", language)}</span>
                    </div>
                  </div>

                  {highlights.length > 0 ? (
                    <div className="provider-evidence" style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap", marginTop: "0.25rem" }}>
                      {highlights.map((highlight) => (
                        <span key={highlight} className="tag" style={{ fontSize: "0.7rem", padding: "2px 6px" }}>{highlight}</span>
                      ))}
                    </div>
                  ) : null}

                  {item.last_error ? (
                    <div className="error-box" style={{ padding: "0.4rem 0.6rem", fontSize: "0.75rem", margin: 0 }}>{item.last_error}</div>
                  ) : null}
                </article>
              );
            })}
          </div>
        ) : null}

        {!loading && visibleItems.length < data.items.length ? (
          <div className="provider-empty muted" ref={loadMoreRef}>
            <span>{t("common.loading")}</span>
          </div>
        ) : null}

        <div className="record-actions" style={{ display: "flex", justifyContent: "space-between", marginTop: "1rem" }}>
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
