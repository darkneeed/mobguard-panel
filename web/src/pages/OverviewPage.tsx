import { Link } from "react-router-dom";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import {
  Cpu,
  Layers,
  HardDrive,
  Clock,
  Terminal,
  Users,
  ShieldAlert,
  Shield,
  Activity,
  ListOrdered
} from "lucide-react";

import {
  api,
  ModuleListResponse,
  ModuleRecord,
  OverviewMetricsResponse,
  Session,
} from "../api/client";
import { prefetchRouteModule } from "../app/routeModules";
import { useI18n } from "../localization";
import {
  automationGuardrailLabels,
  automationModeLabel,
  automationModeReasonLabels,
} from "../shared/automationStatus";
import { useVisiblePolling } from "../shared/useVisiblePolling";
import { formatDisplayDateTime } from "../utils/datetime";
import { useState, useMemo } from "react";

const OVERVIEW_REFRESH_MS = 10000;

function formatBytes(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let size = Math.max(value, 0);
  let unit = units[0];
  for (const candidate of units) {
    unit = candidate;
    if (size < 1024 || candidate === units[units.length - 1]) break;
    size /= 1024;
  }
  const digits = size >= 100 ? 0 : size >= 10 ? 1 : 2;
  return `${size.toFixed(digits)} ${unit}`;
}

function formatPercent(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(1)}%`;
}

function formatAge(seconds?: number | null): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "—";
  const total = Math.max(Math.round(seconds), 0);
  if (total < 60) return `${total}s`;
  if (total < 3600) return `${Math.round(total / 60)}m`;
  if (total < 86400) return `${Math.round(total / 3600)}h`;
  return `${Math.round(total / 86400)}d`;
}

function formatDuration(seconds?: number | null): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "—";
  const total = Math.max(Math.round(seconds), 0);
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (days > 0) return `${days}д ${hours}ч`;
  if (hours > 0) return `${hours}ч ${minutes}м`;
  return `${minutes}м`;
}

function percent(used?: number | null, total?: number | null): number | null {
  if (used === null || used === undefined || total === null || total === undefined || total <= 0) {
    return null;
  }
  return (used / total) * 100;
}

// Map metric status classes to theme values
function metricVariant(value?: number | null, warn = 75, error = 90): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "severity-low";
  if (value >= error) return "severity-critical";
  if (value >= warn) return "severity-high";
  return "status-resolved";
}

function meterWidth(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "0%";
  return `${Math.min(Math.max(value, 0), 100)}%`;
}

function moduleVariant(module: ModuleRecord): string {
  if (module.install_state === "pending_install") return "review-only";
  const system = module.runtime_metrics?.system;
  if (
    !module.healthy ||
    module.health_status === "error" ||
    (system?.cpu_percent ?? 0) >= 92 ||
    (system?.memory_percent ?? 0) >= 95 ||
    (system?.disk_percent ?? 0) >= 95
  ) {
    return "punitive";
  }
  if (
    module.health_status === "warn" ||
    (system?.cpu_percent ?? 0) >= 75 ||
    (system?.memory_percent ?? 0) >= 85 ||
    (system?.disk_percent ?? 0) >= 88
  ) {
    return "severity-high";
  }
  return "status-resolved";
}

function moduleStatusText(module: ModuleRecord): string {
  if (module.install_state === "pending_install") return "Ожидает установку";
  if (!module.healthy) return "Не отвечает";
  if (module.health_status === "error") return "Ошибка";
  if (module.health_status === "warn") return "Предупреждение";
  return "Норма";
}

export function OverviewPage({ session: _session }: { session?: Session }) {
  const { t, language } = useI18n();
  const [overview, setOverview] = useState<OverviewMetricsResponse | null>(null);
  const [modules, setModules] = useState<ModuleListResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastLoadedAt, setLastLoadedAt] = useState("");

  async function load() {
    try {
      const [overviewPayload, modulesPayload] = await Promise.all([
        api.getOverview(),
        api.getModules(),
      ]);
      setOverview(overviewPayload as OverviewMetricsResponse);
      setModules(modulesPayload as ModuleListResponse);
      setError("");
      setLastLoadedAt(new Date().toISOString());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("overview.errors.loadFailed"));
    } finally {
      setLoading(false);
    }
  }

  useVisiblePolling(true, load, OVERVIEW_REFRESH_MS, [t]);

  const queue = overview?.latest_cases || null;
  const pipeline = overview?.pipeline || null;
  const enforcement = overview?.enforcement || null;
  const realtimeUsage = overview?.realtime_usage || null;
  const panelServer = overview?.panel_server || null;
  const summary = modules?.summary || null;
  const modulesOnlineFromItems = useMemo(
    () =>
      (modules?.items || []).reduce(
        (total, item) => total + Math.max(Number(item.runtime_metrics?.active_users ?? 0), 0),
        0,
      ),
    [modules?.items],
  );
  const modulesOnline = Math.max(
    Number(realtimeUsage?.active_users ?? 0),
    Number(summary?.active_users_total ?? 0),
    modulesOnlineFromItems,
  );
  const violatingNowRaw = Number(realtimeUsage?.violating_users ?? 0);
  const compliantNowRaw = Number(realtimeUsage?.compliant_users ?? 0);
  const violatingNow = Math.max(Math.min(violatingNowRaw, modulesOnline), 0);
  const classifiedNow = violatingNowRaw + compliantNowRaw;
  const compliantNow =
    classifiedNow > 0
      ? Math.max(Math.min(compliantNowRaw, modulesOnline - violatingNow), 0)
      : Math.max(modulesOnline - violatingNow, 0);
  const staleSnapshot = (overview?.freshness?.overview_age_seconds ?? 0) > 20;
  const staleModules = modules?.items.filter((item) => !item.healthy) || [];
  const warningModules = modules?.items.filter((item) => moduleVariant(item) === "severity-high") || [];
  const automationModeReasons = automationModeReasonLabels(t, overview?.automation_status);
  const automationGuardrails = automationGuardrailLabels(t, overview?.automation_status);
  const automationMode = automationModeLabel(t, overview?.automation_status);
  const automationModeBadgeClass =
    overview?.automation_status?.mode === "enforce"
      ? "status-resolved"
      : overview?.automation_status?.mode === "warning_only"
        ? "severity-high"
        : "review-only";
  const topModules = useMemo(
    () =>
      [...(modules?.items || [])]
        .sort((left, right) => {
          const rank = (item: ModuleRecord) => {
            const variant = moduleVariant(item);
            if (variant === "punitive") return 0;
            if (variant === "severity-high") return 1;
            if (variant === "review-only") return 2;
            return 3;
          };
          const diff = rank(left) - rank(right);
          if (diff !== 0) return diff;
          return (right.runtime_metrics?.active_users ?? 0) - (left.runtime_metrics?.active_users ?? 0);
        })
        .slice(0, 3),
    [modules?.items],
  );

  function renderMeter(label: string, value?: number | null, warn = 75, error = 90) {
    const variant = metricVariant(value, warn, error);
    return (
      <div className="module-meter">
        <div className="module-meter-head">
          <span>{label}</span>
          <strong>{formatPercent(value)}</strong>
        </div>
        <div className="module-meter-track">
          <span className={`module-meter-fill ${variant}`} style={{ width: meterWidth(value) }} />
        </div>
      </div>
    );
  }

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <h1>Главная</h1>
          <p className="page-lede">
            Состояние сервера панели, модулей и очереди. Данные обновляются автоматически.
          </p>
        </div>
        <div className="dashboard-meta">
          <span className={`status-badge ${summary && (summary.error_modules > 0 || summary.stale_modules > 0) ? "punitive" : summary && summary.warning_modules > 0 ? "severity-high" : "status-resolved"}`}>
            {summary
              ? summary.error_modules > 0 || summary.stale_modules > 0
                ? "Есть критические сигналы"
                : summary.warning_modules > 0
                  ? "Есть предупреждения"
                  : "Все модули в норме"
              : t("common.loading")}
          </span>
          <span className="muted">
            Последняя синхронизация {formatDisplayDateTime(
              panelServer?.collected_at || lastLoadedAt,
              t("common.notAvailable"),
              language,
            )}
          </span>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="stats-grid overview-top-stats">
        <div className="stat-card stat-card-emphasis">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <span>CPU сервера</span>
            <Cpu size={16} style={{ color: "var(--accent)" }} />
          </div>
          <strong>{formatPercent(panelServer?.cpu_percent)}</strong>
        </div>
        <div className="stat-card stat-card-emphasis">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <span>RAM сервера</span>
            <Layers size={16} style={{ color: "var(--accent)" }} />
          </div>
          <strong>{formatPercent(panelServer?.memory_percent)}</strong>
        </div>
        <div className="stat-card stat-card-emphasis">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <span>Диск сервера</span>
            <HardDrive size={16} style={{ color: "var(--accent)" }} />
          </div>
          <strong>{formatPercent(panelServer?.disk_percent)}</strong>
        </div>
        <div className="stat-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <span>Uptime панели</span>
            <Clock size={16} style={{ color: "var(--muted)" }} />
          </div>
          <strong>{formatDuration(panelServer?.uptime_seconds)}</strong>
        </div>
        <div className="stat-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <span>RSS API</span>
            <Terminal size={16} style={{ color: "var(--muted)" }} />
          </div>
          <strong>{formatBytes(panelServer?.api_process_rss_bytes)}</strong>
        </div>
        <div className="stat-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <span>Онлайн на модулях</span>
            <Users size={16} style={{ color: "var(--muted)" }} />
          </div>
          <strong>{modulesOnline}</strong>
        </div>
        <div className="stat-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <span>С ограничениями</span>
            <ShieldAlert size={16} style={{ color: "var(--danger)" }} />
          </div>
          <strong>{violatingNow}</strong>
        </div>
        <div className="stat-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <span>В норме</span>
            <Shield size={16} style={{ color: "var(--success)" }} />
          </div>
          <strong>{compliantNow}</strong>
        </div>
        <div className="stat-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <span>События за окно</span>
            <Activity size={16} style={{ color: "var(--muted)" }} />
          </div>
          <strong>{summary?.recent_events_total ?? "—"}</strong>
        </div>
        <div className="stat-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
            <span>Очередь</span>
            <ListOrdered size={16} style={{ color: "var(--muted)" }} />
          </div>
          <strong>{pipeline?.queue_depth ?? "—"}</strong>
        </div>
      </div>

      {!loading ? (
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
                {overview?.automation_status?.mode === "enforce"
                  ? "Все ограничения применяются на Remnawave в реальном времени автоматически."
                  : overview?.automation_status?.mode === "warning_only"
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
            <Link className="button-link ghost" to="/decisions">
              История авто-решений
            </Link>
          </div>
        </div>
      ) : null}

      <div className="dashboard-grid dashboard-grid-hero overview-split-grid">
        <div className="panel panel-hero">
          <div className="panel-heading panel-heading-row">
            <div>
              <h2>Сервер панели</h2>
              <p className="muted">
                Ядра {panelServer?.cpu_cores ?? "—"} · load {panelServer?.load_avg_1m?.toFixed(2) ?? "—"} / {panelServer?.load_avg_5m?.toFixed(2) ?? "—"} / {panelServer?.load_avg_15m?.toFixed(2) ?? "—"}
              </p>
            </div>
          </div>
          <div className="overview-server-grid stats-grid">
            <div className="module-ops-chip">
              <span>RAM</span>
              <strong>{formatBytes(panelServer?.memory_used_bytes)} / {formatBytes(panelServer?.memory_total_bytes)}</strong>
            </div>
            <div className="module-ops-chip">
              <span>Диск</span>
              <strong>{formatBytes(panelServer?.disk_used_bytes)} / {formatBytes(panelServer?.disk_total_bytes)}</strong>
            </div>
            <div className="module-ops-chip">
              <span>Активные ограничения</span>
              <strong>{enforcement?.active_total ?? "—"}</strong>
            </div>
            <div className="module-ops-chip">
              <span>Нарушают правила</span>
              <strong>{violatingNow}</strong>
            </div>
            <div className="module-ops-chip">
              <span>В норме</span>
              <strong>{compliantNow}</strong>
            </div>
            <div className="module-ops-chip">
              <span>Проблемных модулей</span>
              <strong>{(summary?.warning_modules ?? 0) + (summary?.error_modules ?? 0) + (summary?.stale_modules ?? 0)}</strong>
            </div>
          </div>
          <div className="module-meters">
            {renderMeter("CPU", panelServer?.cpu_percent, 70, 90)}
            {renderMeter("RAM", panelServer?.memory_percent, 78, 90)}
            {renderMeter("Диск", panelServer?.disk_percent, 82, 92)}
          </div>
          <div className="overview-alert-strip">
            {staleSnapshot ? <span className="tag severity-high">Снимок обзора устарел</span> : null}
            {staleModules.length > 0 ? <span className="tag punitive">{staleModules.length} модулей не отвечают</span> : null}
            {warningModules.length > 0 ? <span className="tag severity-high">{warningModules.length} модулей требуют внимания</span> : null}
            {(pipeline?.failed_count ?? 0) > 0 ? <span className="tag punitive">Ошибки очереди: {pipeline?.failed_count ?? 0}</span> : null}
            {!staleSnapshot && staleModules.length === 0 && warningModules.length === 0 && (pipeline?.failed_count ?? 0) === 0 ? (
              <span className="tag status-resolved">Фоновые сервисы выглядят стабильно</span>
            ) : null}
          </div>
        </div>

        <div className="panel" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <div className="panel-heading">
              <h2>Поток обработки</h2>
              <p className="muted">
                Очередь, лаг и активные ограничения.
              </p>
            </div>
            <div className="stats-grid overview-flow-grid" style={{ marginTop: "1rem" }}>
              <div className="stat-card">
                <span>Открытая очередь</span>
                <strong>{queue?.count ?? "—"}</strong>
              </div>
              <div className="stat-card">
                <span>Глубина очереди</span>
                <strong>{pipeline?.queue_depth ?? "—"}</strong>
              </div>
              <div className="stat-card">
                <span>Лаг</span>
                <strong>{formatAge(pipeline?.current_lag_seconds)}</strong>
              </div>
              <div className="stat-card">
                <span>Pending remote</span>
                <strong>{pipeline?.enforcement_pending_count ?? "—"}</strong>
              </div>
            </div>
          </div>

          {(compliantNow > 0 || violatingNow > 0) && (
            <div style={{ marginTop: "1.25rem", borderTop: "1px solid var(--line)", paddingTop: "1rem" }}>
              <span style={{ fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--muted)" }}>
                Соотношение трафика
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginTop: "0.5rem" }}>
                <div style={{ width: "80px", height: "80px", flexShrink: 0 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={[
                          { name: "В норме", value: compliantNow },
                          { name: "С ограничениями", value: violatingNow }
                        ]}
                        dataKey="value"
                        innerRadius={20}
                        outerRadius={36}
                        stroke="none"
                      >
                        <Cell fill="var(--success, #10b981)" />
                        <Cell fill="var(--danger, #ef4444)" />
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem", fontSize: "0.8rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <span style={{ display: "inline-block", width: "8px", height: "8px", borderRadius: "50%", background: "var(--success, #10b981)" }} />
                    <span style={{ color: "var(--muted)" }}>В норме:</span>
                    <strong>{compliantNow} ({Math.round(compliantNow / (compliantNow + violatingNow || 1) * 100)}%)</strong>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <span style={{ display: "inline-block", width: "8px", height: "8px", borderRadius: "50%", background: "var(--danger, #ef4444)" }} />
                    <span style={{ color: "var(--muted)" }}>Ограничены:</span>
                    <strong>{violatingNow} ({Math.round(violatingNow / (compliantNow + violatingNow || 1) * 100)}%)</strong>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="record-meta overview-flow-meta">
            <span>{pipeline?.queued_count ?? 0} в очереди</span>
            <span>{pipeline?.processing_count ?? 0} обрабатывается</span>
            <span>Ошибок {pipeline?.failed_count ?? 0}</span>
            <span>Последний drain {formatDisplayDateTime(pipeline?.last_successful_drain_at || "", t("common.notAvailable"), language)}</span>
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
        <div className="panel">
          <div className="panel-heading panel-heading-row">
            <div>
              <h2>Модули</h2>
              <p className="muted">
                Список подключенных модулей анализа и их текущий статус.
              </p>
            </div>
            <Link
              className="button-link ghost"
              to="/modules"
              onMouseEnter={() => prefetchRouteModule("/modules")}
              onFocus={() => prefetchRouteModule("/modules")}
            >
              Все модули
            </Link>
          </div>
          <div className="record-list">
            {modules?.items.length ? (
              modules.items.map((module) => (
                <Link
                  key={module.module_id}
                  to="/modules"
                  className="record-item inline-link"
                  onMouseEnter={() => prefetchRouteModule("/modules")}
                  onFocus={() => prefetchRouteModule("/modules")}
                >
                  <div className="record-main">
                    <span className="record-title" style={{ fontWeight: 600 }}>{module.module_name}</span>
                    <span className="muted" style={{ fontSize: "0.8rem", marginLeft: "0.5rem" }}>({module.module_id})</span>
                  </div>
                  <div>
                    <span className={`status-badge ${moduleVariant(module)}`}>
                      {moduleStatusText(module)}
                    </span>
                  </div>
                </Link>
              ))
            ) : (
              <div className="provider-empty">Нет подключенных модулей</div>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
