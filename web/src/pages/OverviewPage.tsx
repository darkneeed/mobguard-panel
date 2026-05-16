import { Link } from "react-router-dom";

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
  const staleSnapshot = (overview?.freshness?.overview_age_seconds ?? 0) > 20;
  const staleModules = modules?.items.filter((item) => !item.healthy) || [];
  const warningModules = modules?.items.filter((item) => moduleVariant(item) === "severity-high") || [];
  const automationModeReasons = automationModeReasonLabels(t, overview?.automation_status);
  const automationGuardrails = automationGuardrailLabels(t, overview?.automation_status);
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
          <span>CPU сервера</span>
          <strong>{formatPercent(panelServer?.cpu_percent)}</strong>
        </div>
        <div className="stat-card stat-card-emphasis">
          <span>RAM сервера</span>
          <strong>{formatPercent(panelServer?.memory_percent)}</strong>
        </div>
        <div className="stat-card stat-card-emphasis">
          <span>Диск сервера</span>
          <strong>{formatPercent(panelServer?.disk_percent)}</strong>
        </div>
        <div className="stat-card">
          <span>Uptime панели</span>
          <strong>{formatDuration(panelServer?.uptime_seconds)}</strong>
        </div>
        <div className="stat-card">
          <span>RSS API</span>
          <strong>{formatBytes(panelServer?.api_process_rss_bytes)}</strong>
        </div>
        <div className="stat-card">
          <span>Онлайн на модулях</span>
          <strong>{realtimeUsage?.active_users ?? summary?.active_users_total ?? "—"}</strong>
        </div>
        <div className="stat-card">
          <span>В нарушении</span>
          <strong>{realtimeUsage?.violating_users ?? "—"}</strong>
        </div>
        <div className="stat-card">
          <span>Без нарушения</span>
          <strong>{realtimeUsage?.compliant_users ?? "—"}</strong>
        </div>
        <div className="stat-card">
          <span>События за окно</span>
          <strong>{summary?.recent_events_total ?? "—"}</strong>
        </div>
        <div className="stat-card">
          <span>Очередь</span>
          <strong>{pipeline?.queue_depth ?? "—"}</strong>
        </div>
      </div>

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
          <div className="overview-server-grid">
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
              <span>Сейчас нарушают</span>
              <strong>{realtimeUsage?.violating_users ?? "—"}</strong>
            </div>
            <div className="module-ops-chip">
              <span>Сейчас по правилам</span>
              <strong>{realtimeUsage?.compliant_users ?? "—"}</strong>
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

        <div className="panel">
          <div className="panel-heading">
            <h2>Поток обработки</h2>
            <p className="muted">
              Очередь, лаг и активные санкции без тяжёлых вспомогательных карточек.
            </p>
          </div>
          <div className="stats-grid overview-flow-grid">
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
        <>
          <div className="panel">
            <div className="panel-heading">
              <h2>Автоматические решения</h2>
              <p className="muted">
                Текущие решения принимаются на основе настроек и обучения.
              </p>
            </div>
              <div className="detail-list">
                <div>
                  <dt>Эффективный режим</dt>
                  <dd>{automationModeLabel(t, overview?.automation_status)}</dd>
                </div>
                <div>
                  <dt>Почему сейчас так</dt>
                  <dd>
                    {automationModeReasons.length
                      ? automationModeReasons.join(", ")
                      : "Блокирующих режим факторов нет"}
                  </dd>
                </div>
                <div>
                  <dt>Ограничители</dt>
                  <dd>
                    {automationGuardrails.length
                      ? automationGuardrails.join(", ")
                      : "Дополнительные guardrail-флаги не включены"}
                  </dd>
                </div>
              </div>
            <div className="action-row">
              <Link className="button-link ghost" to="/rules/general">
                Настроить правила
              </Link>
              <Link className="button-link ghost" to="/decisions">
                Открыть решения
              </Link>
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading panel-heading-row">
              <div>
                <h2>Модули</h2>
                <p className="muted">
                  Общий онлайн по модулям и текущая нагрузка по каждому.
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
            <div className="queue-grid module-ops-grid-list">
              {topModules.map((module) => {
                const system = module.runtime_metrics?.system;
                return (
                  <div className="queue-card module-ops-card module-ops-card-compact" key={module.module_id}>
                    <div className="queue-card-top">
                      <div>
                        <strong>{module.module_name}</strong>
                        <div className="queue-card-identifiers">
                          <span>{module.module_id}</span>
                          <span>{module.version || "—"}</span>
                        </div>
                      </div>
                      <span className={`status-badge module-status-pill ${moduleVariant(module)}`}>
                        {moduleStatusText(module)}
                      </span>
                    </div>
                    <div className="module-ops-grid">
                      <div className="module-ops-chip">
                        <span>Онлайн</span>
                        <strong>{module.runtime_metrics?.active_users ?? 0}</strong>
                      </div>
                      <div className="module-ops-chip">
                        <span>События</span>
                        <strong>{module.runtime_metrics?.recent_events ?? 0}</strong>
                      </div>
                    </div>
                    <div className="module-meters">
                      {renderMeter("CPU", system?.cpu_percent, 75, 90)}
                      {renderMeter("RAM", system?.memory_percent, 80, 92)}
                      {renderMeter("Диск", system?.disk_percent, 82, 92)}
                    </div>
                    <div className="record-meta module-ops-meta">
                      <span>RSS {formatBytes(module.runtime_metrics?.processes?.rss_bytes)}</span>
                      <span>Spool {module.spool_depth}</span>
                      <span>Heartbeat {formatAge(module.seconds_since_last_seen)}</span>
                    </div>
                    {module.error_text ? <div className="error-box module-inline-error">{module.error_text}</div> : null}
                  </div>
                );
              })}
            </div>
          </div>
          <div className="panel">
            <div className="panel-heading">
              <h2>Последние кейсы</h2>
              <p className="muted">Свежие спорные кейсы без лишнего служебного шума.</p>
            </div>
            <div className="record-list">
              {queue?.items.length ? (
                queue.items.slice(0, 5).map((item) => (
                  <Link
                    key={item.id}
                    to={`/reviews/${item.id}`}
                    className="record-item inline-link"
                    onMouseEnter={() => prefetchRouteModule(`/reviews/${item.id}`)}
                    onFocus={() => prefetchRouteModule(`/reviews/${item.id}`)}
                  >
                    <div className="record-main">
                      <span className="record-title">#{item.id} · {item.username || item.uuid || item.ip}</span>
                      <span className="tag">{item.review_reason}</span>
                    </div>
                    <div className="record-meta">
                      <span>{item.ip}</span>
                      <span>{formatDisplayDateTime(item.updated_at, t("common.notAvailable"), language)}</span>
                    </div>
                  </Link>
                ))
              ) : (
                <div className="provider-empty">Открытых кейсов сейчас нет</div>
              )}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
