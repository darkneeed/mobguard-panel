import { FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { hasPermission } from "../app/permissions";
import { prefetchRouteModule } from "../app/routeModules";
import {
  api,
  ModuleListResponse,
  ModuleRecord,
  OverviewMetricsResponse,
  Session,
  UserSearchResponse,
} from "../api/client";
import { useI18n } from "../localization";
import { useVisiblePolling } from "../shared/useVisiblePolling";
import { formatDisplayDateTime } from "../utils/datetime";

const OVERVIEW_REFRESH_MS = 30000;
const OVERVIEW_STALE_AFTER_SECONDS = 15;

function formatBytes(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let size = Math.max(value, 0);
  let unit = units[0];
  for (const candidate of units) {
    unit = candidate;
    if (size < 1024 || candidate === units[units.length - 1]) {
      break;
    }
    size /= 1024;
  }
  const digits = size >= 100 ? 0 : size >= 10 ? 1 : 2;
  return `${size.toFixed(digits)} ${unit}`;
}

function formatRate(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return `${formatBytes(value)}/s`;
}

function formatPercent(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return `${value.toFixed(1)}%`;
}

function formatAge(seconds?: number | null): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) {
    return "—";
  }
  const total = Math.max(Math.round(seconds), 0);
  if (total < 60) return `${total}s`;
  if (total < 3600) return `${Math.round(total / 60)}m`;
  if (total < 86400) return `${Math.round(total / 3600)}h`;
  return `${Math.round(total / 86400)}d`;
}

function summaryPercent(used?: number | null, total?: number | null): number | null {
  if (used === null || used === undefined || total === null || total === undefined || total <= 0) {
    return null;
  }
  return (used / total) * 100;
}

function metricVariant(value?: number | null, warn = 75, error = 90): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "severity-low";
  }
  if (value >= error) return "severity-critical";
  if (value >= warn) return "severity-high";
  return "status-resolved";
}

function meterWidth(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "0%";
  }
  return `${Math.min(Math.max(value, 0), 100)}%`;
}

function moduleVariant(module: ModuleRecord): string {
  const system = module.runtime_metrics?.system;
  if (module.install_state === "pending_install") {
    return "review-only";
  }
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

export function OverviewPage({ session }: { session?: Session }) {
  const { t, language } = useI18n();
  const [overview, setOverview] = useState<OverviewMetricsResponse | null>(null);
  const [modules, setModules] = useState<ModuleListResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastLoadedAt, setLastLoadedAt] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResult, setSearchResult] = useState<UserSearchResponse | null>(null);
  const [searchError, setSearchError] = useState("");
  const [searchPending, setSearchPending] = useState(false);
  const canReadData = session ? hasPermission(session, "data.read") : true;

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
      setError(
        err instanceof Error ? err.message : t("overview.errors.loadFailed"),
      );
    } finally {
      setLoading(false);
    }
  }

  useVisiblePolling(true, load, OVERVIEW_REFRESH_MS, [t]);

  async function searchUsers(event?: FormEvent) {
    event?.preventDefault();
    const query = searchQuery.trim();
    if (!query) return;
    setSearchPending(true);
    setSearchError("");
    try {
      const payload = (await api.searchUsers(query)) as UserSearchResponse;
      setSearchResult(payload);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Не удалось выполнить поиск");
    } finally {
      setSearchPending(false);
    }
  }

  const freshness = overview?.freshness || null;
  const queue = overview?.latest_cases || null;
  const pipeline = overview?.pipeline || null;
  const enforcement = overview?.enforcement || null;
  const summary = modules?.summary;
  const overviewStale = Boolean(
    (freshness?.overview_age_seconds ?? 0) > OVERVIEW_STALE_AFTER_SECONDS,
  );

  const attentionItems = useMemo(() => {
    const items: string[] = [];
    if (overviewStale) {
      items.push(t("overview.attentionItems.overviewStale"));
    }
    if ((pipeline?.failed_count ?? 0) > 0) {
      items.push(
        t("overview.attentionItems.failedQueue", {
          count: pipeline?.failed_count ?? 0,
        }),
      );
    }
    if ((summary?.stale_modules ?? 0) > 0) {
      items.push(t("overview.attentionItems.staleModules", { count: summary?.stale_modules ?? 0 }));
    }
    if ((summary?.warning_modules ?? 0) > 0 || (summary?.error_modules ?? 0) > 0) {
      items.push(`Модули с риском: ${(summary?.warning_modules ?? 0) + (summary?.error_modules ?? 0)}`);
    }
    if ((enforcement?.active_total ?? 0) > 0) {
      items.push(
        t("overview.attentionItems.activeViolations", {
          count: enforcement?.active_total ?? 0,
        }),
      );
    }
    if (!items.length) {
      items.push(t("overview.attentionItems.quiet"));
    }
    return items;
  }, [enforcement?.active_total, overviewStale, pipeline?.failed_count, summary?.error_modules, summary?.stale_modules, summary?.warning_modules, t]);

  const topModules = useMemo(() => {
    return [...(modules?.items || [])].sort((left, right) => {
      const rank = (item: ModuleRecord) => {
        const variant = moduleVariant(item);
        if (variant === "punitive") return 0;
        if (variant === "severity-high") return 1;
        return 2;
      };
      const diff = rank(left) - rank(right);
      if (diff !== 0) return diff;
      return (right.runtime_metrics?.active_users ?? 0) - (left.runtime_metrics?.active_users ?? 0);
    });
  }, [modules?.items]);

  function renderMetricMeter(label: string, value?: number | null, warn = 75, error = 90) {
    const variant = metricVariant(value, warn, error);
    return (
      <div className="module-meter">
        <div className="module-meter-head">
          <span>{label}</span>
          <strong>{formatPercent(value)}</strong>
        </div>
        <div className="module-meter-track">
          <span
            className={`module-meter-fill ${variant}`}
            style={{ width: meterWidth(value) }}
          />
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
            Состояние серверов и модулей, общий онлайн по активности, нагрузка и быстрый доступ к пользователям.
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
            {t("overview.lastUpdated", {
              value: formatDisplayDateTime(
                freshness?.overview_updated_at || lastLoadedAt,
                t("common.notAvailable"),
                language,
              ),
            })}
          </span>
        </div>
      </div>

      {error ? (
        <div className="error-box">
          {error}
          {overview
            ? ` ${t("overview.errors.showingLastGood", {
                value: formatAge(freshness?.overview_age_seconds),
              })}`
            : ""}
        </div>
      ) : null}

      <div className="stats-grid">
        <div className="stat-card">
          <span>Онлайн на модулях</span>
          <strong>{summary?.active_users_total ?? "—"}</strong>
        </div>
        <div className="stat-card">
          <span>Модули в норме</span>
          <strong>{summary?.healthy_modules ?? "—"}</strong>
        </div>
        <div className="stat-card">
          <span>Внимание / ошибки</span>
          <strong>
            {summary ? `${summary.warning_modules + summary.error_modules}` : "—"}
          </strong>
        </div>
        <div className="stat-card">
          <span>События за окно</span>
          <strong>{summary?.recent_events_total ?? "—"}</strong>
        </div>
        <div className="stat-card">
          <span>Средний CPU</span>
          <strong>{formatPercent(summary?.avg_cpu_percent)}</strong>
        </div>
        <div className="stat-card">
          <span>RAM</span>
          <strong>{formatPercent(summaryPercent(summary?.memory_used_bytes, summary?.memory_total_bytes))}</strong>
        </div>
        <div className="stat-card">
          <span>Диск</span>
          <strong>{formatPercent(summaryPercent(summary?.disk_used_bytes, summary?.disk_total_bytes))}</strong>
        </div>
        <div className="stat-card">
          <span>MobGuard RSS</span>
          <strong>{formatBytes(summary?.mobguard_process_rss_bytes)}</strong>
        </div>
      </div>

      <div className="dashboard-grid dashboard-grid-hero overview-split-grid">
        <div className="panel panel-hero">
          <div className="panel-heading panel-heading-row">
            <div>
              <h2>Ресурсы и состояние</h2>
              <p className="muted">
                Сводка по последним heartbeat’ам модулей и активности пользователей за окно {summary?.activity_window_seconds ? `${Math.round(summary.activity_window_seconds / 60)} минут` : "активности"}.
              </p>
            </div>
            <Link
              className="button-link"
              to="/modules"
              onMouseEnter={() => prefetchRouteModule("/modules")}
              onFocus={() => prefetchRouteModule("/modules")}
            >
              Открыть модули
            </Link>
          </div>
          <div className="record-grid">
            <div className="record-kv">
              <strong>RAM</strong>
              <span>{formatBytes(summary?.memory_used_bytes)} / {formatBytes(summary?.memory_total_bytes)}</span>
            </div>
            <div className="record-kv">
              <strong>Диск</strong>
              <span>{formatBytes(summary?.disk_used_bytes)} / {formatBytes(summary?.disk_total_bytes)}</span>
            </div>
            <div className="record-kv">
              <strong>Пик CPU</strong>
              <span>{formatPercent(summary?.peak_cpu_percent)}</span>
            </div>
            <div className="record-kv">
              <strong>Очередь</strong>
              <span>{pipeline?.queue_depth ?? "—"}</span>
            </div>
            <div className="record-kv">
              <strong>Ошибки конвейера</strong>
              <span>{pipeline?.failed_count ?? "—"}</span>
            </div>
            <div className="record-kv">
              <strong>Активные ограничения</strong>
              <span>{enforcement?.active_total ?? "—"}</span>
            </div>
          </div>
          <div className="record-list overview-signal-list">
            {attentionItems.map((item) => (
              <div className="record-item" key={item}>
                <div className="record-main">
                  <span className="record-title">{item}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading panel-heading-row">
            <div>
              <h2>Поиск пользователя</h2>
              <p className="muted">
                Поиск по UUID, username, Telegram ID или System ID в тех данных, которые уже есть в панели.
              </p>
            </div>
          </div>
          <form className="search-strip compact-search-strip" onSubmit={searchUsers}>
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="UUID / username / Telegram ID / System ID"
            />
            <button type="submit" disabled={searchPending || !searchQuery.trim()}>
              {searchPending ? "Ищу..." : "Найти"}
            </button>
          </form>
          {searchError ? <div className="error-box">{searchError}</div> : null}
          {searchResult?.panel_match ? (
            <div className="tag overview-search-tag">
              Panel match: {String(
                (searchResult.panel_match as Record<string, unknown>).username ||
                  (searchResult.panel_match as Record<string, unknown>).uuid ||
                  (searchResult.panel_match as Record<string, unknown>).id ||
                  "user"
              )}
            </div>
          ) : null}
          <div className="record-list overview-search-results">
            {(searchResult?.items || []).length ? (
              searchResult?.items.map((item) => {
                const identifier = String(item.uuid || item.system_id || item.telegram_id || "");
                const queryValue = String(item.username || item.uuid || item.system_id || item.telegram_id || "");
                return (
                  <Link
                    key={`${identifier}-${queryValue}`}
                    to={`/data/users?identifier=${encodeURIComponent(identifier)}&query=${encodeURIComponent(queryValue)}`}
                    className="record-item inline-link"
                    onMouseEnter={() => prefetchRouteModule("/data/users")}
                    onFocus={() => prefetchRouteModule("/data/users")}
                  >
                    <div className="record-main">
                      <span className="record-title">
                        {String(item.username || item.uuid || item.system_id || item.telegram_id)}
                      </span>
                      <span className="tag">Открыть карточку</span>
                    </div>
                    <div className="record-meta">
                      <span>UUID: {String(item.uuid || "—")}</span>
                      <span>System ID: {String(item.system_id ?? "—")}</span>
                      <span>Telegram ID: {String(item.telegram_id || "—")}</span>
                    </div>
                  </Link>
                );
              })
            ) : searchResult ? (
              <div className="provider-empty">Совпадений не найдено</div>
            ) : (
              <div className="provider-empty">Введите идентификатор и выполните поиск</div>
            )}
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
            <div className="panel-heading panel-heading-row">
              <div>
                <h2>Модули и серверная нагрузка</h2>
                <p className="muted">
                  По каждому модулю: онлайн за окно активности, нагрузка сервера и использование ресурсов процессами MobGuard.
                </p>
              </div>
            </div>
            <div className="queue-grid module-ops-grid-list">
              {topModules.map((module) => {
                const system = module.runtime_metrics?.system;
                return (
                  <div className={`queue-card module-ops-card`} key={module.module_id}>
                    <div className="queue-card-top">
                      <div>
                        <strong>{module.module_name}</strong>
                        <div className="queue-card-identifiers">
                          <span>{module.module_id}</span>
                          <span>{module.version || "—"}</span>
                        </div>
                      </div>
                      <span className={`status-badge ${moduleVariant(module)}`}>
                        {module.install_state === "pending_install"
                          ? "pending"
                          : !module.healthy
                          ? "offline"
                          : module.health_status === "error"
                            ? "error"
                            : module.health_status === "warn"
                              ? "warn"
                              : "ok"}
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
                      <div className="module-ops-chip">
                        <span>MobGuard RSS</span>
                        <strong>{formatBytes(module.runtime_metrics?.processes?.rss_bytes)}</strong>
                      </div>
                      <div className="module-ops-chip">
                        <span>Spool</span>
                        <strong>{module.spool_depth}</strong>
                      </div>
                    </div>

                    <div className="module-meters">
                      {renderMetricMeter("CPU", system?.cpu_percent)}
                      {renderMetricMeter("RAM", system?.memory_percent)}
                      {renderMetricMeter("Диск", system?.disk_percent, 80, 92)}
                    </div>

                    <div className="record-meta">
                      <span>Load {system?.load_avg_1m?.toFixed(2) ?? "—"} / {system?.load_avg_5m?.toFixed(2) ?? "—"} / {system?.load_avg_15m?.toFixed(2) ?? "—"}</span>
                      <span>RAM {formatBytes(system?.memory_used_bytes)} / {formatBytes(system?.memory_total_bytes)}</span>
                      <span>Disk {formatBytes(system?.disk_used_bytes)} / {formatBytes(system?.disk_total_bytes)}</span>
                      <span>I/O {formatRate(system?.disk_read_bps)} ↓ / {formatRate(system?.disk_write_bps)} ↑</span>
                      <span>Heartbeat {formatAge(module.seconds_since_last_seen)}</span>
                    </div>

                    {module.error_text ? <div className="error-box">{module.error_text}</div> : null}

                    <div className="action-row">
                      <Link
                        className="ghost button-link"
                        to="/modules"
                        onMouseEnter={() => prefetchRouteModule("/modules")}
                        onFocus={() => prefetchRouteModule("/modules")}
                      >
                        Перейти к модулю
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="dashboard-grid">
            <div className="panel">
              <div className="panel-heading panel-heading-row">
                <div>
                  <h2>Очередь и доставка</h2>
                  <p className="muted">
                    Состояние общего конвейера обработки и удалённых применений.
                  </p>
                </div>
              </div>
              <div className="metric-list">
                <div className="metric-row">
                  <div className="record-main">
                    <span className="record-title">Глубина очереди</span>
                    <span>{pipeline?.queue_depth ?? "—"}</span>
                  </div>
                  <div className="record-meta">
                    {pipeline?.queued_count ?? 0} в очереди · {pipeline?.processing_count ?? 0} обрабатывается
                  </div>
                </div>
                <div className="metric-row">
                  <div className="record-main">
                    <span className="record-title">Ошибки</span>
                    <span>{pipeline?.failed_count ?? "—"}</span>
                  </div>
                  <div className="record-meta">
                    Pending remote: {pipeline?.enforcement_pending_count ?? 0}
                  </div>
                </div>
                <div className="metric-row">
                  <div className="record-main">
                    <span className="record-title">Лаг</span>
                    <span>{formatAge(pipeline?.current_lag_seconds)}</span>
                  </div>
                  <div className="record-meta">
                    Последний drain: {formatDisplayDateTime(
                      pipeline?.last_successful_drain_at || "",
                      t("common.notAvailable"),
                      language,
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-heading panel-heading-row">
                <div>
                  <h2>Последние кейсы</h2>
                  <p className="muted">
                    Быстрый доступ к свежим спорным кейсам из очереди.
                  </p>
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
                        <span>{item.ip}</span>
                        <span>{formatDisplayDateTime(
                          item.updated_at,
                          t("common.notAvailable"),
                          language,
                        )}</span>
                      </div>
                    </Link>
                  ))
                ) : (
                  <div className="provider-empty">Открытых кейсов сейчас нет</div>
                )}
              </div>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
