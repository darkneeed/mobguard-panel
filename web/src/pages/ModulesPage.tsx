import { useMemo, useState } from "react";

import { hasPermission } from "../app/permissions";
import {
  api,
  ModuleDetailResponse,
  ModuleListResponse,
  ModuleProvisioningPayload,
  ModuleRecord,
  Session,
} from "../api/client";
import { ModalShell } from "../components/ModalShell";
import { useToast } from "../components/ToastProvider";
import { useI18n } from "../localization";
import { useVisiblePolling } from "../shared/useVisiblePolling";
import { formatDisplayDateTime } from "../utils/datetime";

type ModuleDraft = {
  module_name: string;
  inbound_tags: string;
};

const MODULES_REFRESH_MS = 15000;

const EMPTY_DRAFT: ModuleDraft = {
  module_name: "",
  inbound_tags: "",
};

function draftFromModule(module: ModuleRecord): ModuleDraft {
  return {
    module_name: module.module_name || "",
    inbound_tags: (module.inbound_tags || []).join("\n"),
  };
}

function toProvisioningPayload(draft: ModuleDraft): ModuleProvisioningPayload {
  return {
    module_name: draft.module_name.trim(),
    inbound_tags: draft.inbound_tags
      .split(/\r?\n|,/)
      .map((item) => item.trim())
      .filter(Boolean),
  };
}

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

function formatPercent(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return `${value.toFixed(1)}%`;
}

function heartbeatVariant(module: ModuleRecord): string {
  if (module.install_state === "pending_install") {
    return "review-only";
  }
  if (!module.healthy) {
    return "severity-critical";
  }
  return "status-resolved";
}

function validationVariant(module: ModuleRecord): string {
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

function heartbeatLabelKey(module: ModuleRecord): string {
  if (module.install_state === "pending_install") {
    return "modules.pendingInstall";
  }
  if (!module.healthy) {
    return "modules.freshness.stale";
  }
  return "modules.freshness.ok";
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

function summaryPercent(used?: number | null, total?: number | null): number | null {
  if (used === null || used === undefined || total === null || total === undefined || total <= 0) {
    return null;
  }
  return (used / total) * 100;
}

export function ModulesPage({ session }: { session?: Session }) {
  const { t, language } = useI18n();
  const { pushToast } = useToast();
  const [data, setData] = useState<ModuleListResponse | null>(null);
  const [detail, setDetail] = useState<ModuleDetailResponse | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [modalMode, setModalMode] = useState<"create" | "detail" | null>(null);
  const [draft, setDraft] = useState<ModuleDraft>(EMPTY_DRAFT);
  const [savedDraft, setSavedDraft] = useState<ModuleDraft>(EMPTY_DRAFT);
  const [revealedToken, setRevealedToken] = useState("");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [panelError, setPanelError] = useState("");
  const [saved, setSaved] = useState("");
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const activeModule = modalMode === "detail" ? (detail?.module ?? null) : null;
  const draftDirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(savedDraft),
    [draft, savedDraft],
  );
  const modalOpen = modalMode !== null;
  const canManageModules = hasPermission(session, "modules.write");
  const canRevealModuleToken = hasPermission(session, "modules.token_reveal");
  const canSubmit =
    modalMode === "create"
      ? draftDirty && Boolean(draft.module_name.trim())
      : draftDirty;

  const filteredItems = useMemo(() => {
    const items = data?.items || [];
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return items;
    return items.filter((item) => {
      const haystack = [
        item.module_name,
        item.module_id,
        item.version,
        ...(item.inbound_tags || []),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [data, query]);

  const installedItems = useMemo(
    () =>
      (data?.items || []).filter(
        (item) => item.install_state !== "pending_install",
      ),
    [data],
  );

  const healthyCount = installedItems.filter(
    (item) => item.healthy && validationVariant(item) === "status-resolved",
  ).length;
  const warnCount = installedItems.filter(
    (item) => item.healthy && validationVariant(item) === "severity-high",
  ).length;
  const errorCount = installedItems.filter(
    (item) => validationVariant(item) === "punitive",
  ).length;
  const staleCount = installedItems.filter((item) => !item.healthy).length;

  async function loadInitialState() {
    try {
      const listPayload = (await api.getModules()) as ModuleListResponse;
      setData(listPayload);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("modules.loadFailed"));
    }
  }

  useVisiblePolling(true, loadInitialState, MODULES_REFRESH_MS, [t]);

  async function openModule(moduleId: string) {
    setModalMode("detail");
    setSelectedId(moduleId);
    setPanelError("");
    setSaved("");
    setRevealedToken("");
    if (detail?.module.module_id === moduleId) {
      return;
    }
    setDetail(null);
    setLoadingDetail(true);
    try {
      const payload = (await api.getModuleDetail(
        moduleId,
      )) as ModuleDetailResponse;
      setDetail(payload);
      const normalizedDraft = draftFromModule(payload.module);
      setDraft(normalizedDraft);
      setSavedDraft(normalizedDraft);
    } catch (err) {
      setPanelError(
        err instanceof Error ? err.message : t("modules.loadFailed"),
      );
    } finally {
      setLoadingDetail(false);
    }
  }

  function startCreateFlow() {
    setModalMode("create");
    setSelectedId("");
    setDetail(null);
    setDraft(EMPTY_DRAFT);
    setSavedDraft(EMPTY_DRAFT);
    setRevealedToken("");
    setPanelError("");
    setSaved("");
  }

  function closeModal() {
    setModalMode(null);
    setPanelError("");
    setSaved("");
    setRevealedToken("");
  }

  async function saveModule() {
    setSubmitting(true);
    setPanelError("");
    setSaved("");
    try {
      const payload = toProvisioningPayload(draft);
      if (modalMode === "create") {
        const response = (await api.createModule(
          payload,
        )) as ModuleDetailResponse;
        const nextDraft = draftFromModule(response.module);
        setModalMode("detail");
        setSelectedId(response.module.module_id);
        setDetail(response);
        setDraft(nextDraft);
        setSavedDraft(nextDraft);
        setRevealedToken(response.install.module_token || "");
        setData((prev) => {
          const nextItems = [
            response.module,
            ...(prev?.items || []).filter(
              (item) => item.module_id !== response.module.module_id,
            ),
          ];
          return {
            items: nextItems,
            count: nextItems.length,
            summary: prev?.summary,
            pipeline: prev?.pipeline,
          };
        });
        setSaved(t("modules.createSuccess"));
      } else if (selectedId) {
        const response = (await api.updateModule(
          selectedId,
          payload,
        )) as ModuleDetailResponse;
        const nextDraft = draftFromModule(response.module);
        setDetail(response);
        setDraft(nextDraft);
        setSavedDraft(nextDraft);
        setData((prev) => ({
          items: (prev?.items || []).map((item) =>
            item.module_id === response.module.module_id
              ? response.module
              : item,
          ),
          count: prev?.count || 0,
          summary: prev?.summary,
          pipeline: prev?.pipeline,
        }));
        setSaved(t("modules.updateSuccess"));
      }
    } catch (err) {
      setPanelError(
        err instanceof Error ? err.message : t("modules.saveFailed"),
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function revealToken() {
    if (!selectedId) return;
    try {
      const response = (await api.revealModuleToken(selectedId)) as {
        module_token: string;
      };
      setRevealedToken(response.module_token || "");
      pushToast("success", t("modules.tokenRevealSuccess"));
    } catch (err) {
      pushToast(
        "error",
        err instanceof Error ? err.message : t("modules.tokenRevealFailed"),
      );
    }
  }

  async function copyText(value: string, successMessage: string) {
    try {
      await navigator.clipboard.writeText(value);
      pushToast("success", successMessage);
    } catch {
      pushToast("error", t("modules.copyFailed"));
    }
  }

  function renderMetricMeter(
    label: string,
    value?: number | null,
    suffix = "%",
    warn = 75,
    error = 90,
  ) {
    const variant = metricVariant(value, warn, error);
    return (
      <div className="module-meter">
        <div className="module-meter-head">
          <span>{label}</span>
          <strong>{value === null || value === undefined ? "—" : `${value.toFixed(1)}${suffix}`}</strong>
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

  function renderModuleCard(item: ModuleRecord) {
    const isActive = modalMode === "detail" && selectedId === item.module_id;
    const runtime = item.runtime_metrics;
    const system = runtime?.system;
    const activeUsers = runtime?.active_users ?? 0;
    const recentEvents = runtime?.recent_events ?? 0;

    return (
      <article
        className={`queue-card module-ops-card ${isActive ? "module-card-active" : ""}`}
        key={item.module_id}
      >
        <div className="queue-card-top">
          <div>
            <strong>{item.module_name}</strong>
            <div className="queue-card-identifiers">
              <span>{t("modules.moduleId", { value: item.module_id })}</span>
              <span>
                {t("modules.version", {
                  value: item.version || t("common.notAvailable"),
                })}
              </span>
              <span>{t("modules.protocol", { value: item.protocol_version || "v1" })}</span>
            </div>
          </div>
          <div className="queue-card-flags">
            <span className={`status-badge ${heartbeatVariant(item)}`}>
              {t(heartbeatLabelKey(item))}
            </span>
            {item.install_state !== "pending_install" ? (
              <span className={`tag ${validationVariant(item)}`}>
                {t(`modules.health.${item.health_status}`)}
              </span>
            ) : null}
          </div>
        </div>

        <div className="module-ops-grid">
          <div className="module-ops-chip">
            <span>Онлайн {runtime?.activity_window_seconds ? `${Math.round(runtime.activity_window_seconds / 60)}м` : ""}</span>
            <strong>{activeUsers}</strong>
          </div>
          <div className="module-ops-chip">
            <span>События {runtime?.activity_window_seconds ? `${Math.round(runtime.activity_window_seconds / 60)}м` : ""}</span>
            <strong>{recentEvents}</strong>
          </div>
          <div className="module-ops-chip">
            <span>Spool</span>
            <strong>{item.spool_depth}</strong>
          </div>
          <div className="module-ops-chip">
            <span>MobGuard RSS</span>
            <strong>{formatBytes(runtime?.processes?.rss_bytes)}</strong>
          </div>
        </div>

        <div className="module-meters">
          {renderMetricMeter("CPU", system?.cpu_percent)}
          {renderMetricMeter("RAM", system?.memory_percent)}
          {renderMetricMeter("Диск", system?.disk_percent, "%", 80, 92)}
        </div>

        <div className="record-grid">
          <div className="record-kv">
            <strong>{t("modules.lastSeen")}</strong>
            <span>
              {formatDisplayDateTime(
                item.last_seen_at,
                t("common.notAvailable"),
                language,
              )}
            </span>
          </div>
          <div className="record-kv">
            <strong>{t("modules.lastHeartbeatAge")}</strong>
            <span>{formatAge(item.seconds_since_last_seen)}</span>
          </div>
          <div className="record-kv">
            <strong>Load avg</strong>
            <span>
              {system?.load_avg_1m !== null && system?.load_avg_1m !== undefined
                ? `${system.load_avg_1m?.toFixed(2)} / ${system.load_avg_5m?.toFixed(2) ?? "0.00"} / ${system.load_avg_15m?.toFixed(2) ?? "0.00"}`
                : "—"}
            </span>
          </div>
          <div className="record-kv">
            <strong>{t("modules.inboundTags")}</strong>
            <span>
              {item.inbound_tags.length
                ? item.inbound_tags.join(", ")
                : t("common.notAvailable")}
            </span>
          </div>
        </div>

        <div className="record-meta">
          <span>RAM {formatBytes(system?.memory_used_bytes)} / {formatBytes(system?.memory_total_bytes)}</span>
          <span>Disk {formatBytes(system?.disk_used_bytes)} / {formatBytes(system?.disk_total_bytes)}</span>
          <span>I/O {formatRate(system?.disk_read_bps)} ↓ / {formatRate(system?.disk_write_bps)} ↑</span>
          <span>{t("modules.accessLogExists")}: {item.access_log_exists ? t("common.yes") : t("common.no")}</span>
        </div>

        {item.error_text ? <div className="error-box">{item.error_text}</div> : null}

        <div className="action-row">
          <button className="ghost" onClick={() => openModule(item.module_id)}>
            {t("modules.open")}
          </button>
        </div>
      </article>
    );
  }

  const summary = data?.summary;

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <h1>{t("modules.title")}</h1>
          <p className="page-lede">{t("modules.description")}</p>
        </div>
        <div className="action-row">
          <span className="chip">
            {t("modules.count", { count: data?.count ?? 0 })}
          </span>
          <button onClick={startCreateFlow} disabled={!canManageModules}>
            {t("modules.create")}
          </button>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="stats-grid">
        <div className="stat-card">
          <span>{t("modules.cards.total")}</span>
          <strong>{data?.count ?? "—"}</strong>
        </div>
        <div className="stat-card">
          <span>{t("modules.cards.healthy")}</span>
          <strong>{data ? healthyCount : "—"}</strong>
        </div>
        <div className="stat-card">
          <span>{t("modules.cards.warn")}</span>
          <strong>{data ? warnCount : "—"}</strong>
        </div>
        <div className="stat-card">
          <span>{t("modules.cards.error")}</span>
          <strong>{data ? errorCount : "—"}</strong>
        </div>
        <div className="stat-card">
          <span>{t("modules.cards.stale")}</span>
          <strong>{data ? staleCount : "—"}</strong>
        </div>
        <div className="stat-card">
          <span>Онлайн модулей</span>
          <strong>{summary?.active_users_total ?? "—"}</strong>
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
          <strong>
            {formatPercent(summaryPercent(summary?.memory_used_bytes, summary?.memory_total_bytes))}
          </strong>
        </div>
        <div className="stat-card">
          <span>Диск</span>
          <strong>
            {formatPercent(summaryPercent(summary?.disk_used_bytes, summary?.disk_total_bytes))}
          </strong>
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading panel-heading-row">
          <div>
            <h2>{t("modules.listTitle")}</h2>
            <p className="muted">{t("modules.listDescription")}</p>
          </div>
          <div className="search-strip compact-search-strip">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Поиск по имени, ID или INBOUND-тегу"
            />
          </div>
        </div>
        <div className="queue-grid module-ops-grid-list">
          {filteredItems.map(renderModuleCard)}
          {!filteredItems.length ? (
            <div className="provider-empty">{t("modules.empty")}</div>
          ) : null}
        </div>
      </div>

      <ModalShell
        open={modalOpen}
        onClose={closeModal}
        title={
          modalMode === "create"
            ? t("modules.createTitle")
            : t("modules.detailsTitle")
        }
        description={
          modalMode === "create"
            ? t("modules.createDescription")
            : t("modules.detailsDescription")
        }
        closeLabel={t("common.close")}
        actions={
          <div className="action-row">
            <span
              className={draftDirty ? "tag review-only" : "tag severity-low"}
            >
              {draftDirty ? t("common.unsavedChanges") : t("common.saved")}
            </span>
            <button
              onClick={saveModule}
              disabled={!canManageModules || submitting || !canSubmit}
            >
              {modalMode === "create" ? t("modules.create") : t("modules.save")}
            </button>
          </div>
        }
      >
        {panelError ? <div className="error-box">{panelError}</div> : null}
        {saved ? <div className="ok-box">{saved}</div> : null}

        <div className="modules-modal-stack">
          <div className="panel">
            <div className="panel-heading">
              <h2>{t("modules.fields.moduleName")}</h2>
              <p className="muted">
                {modalMode === "create"
                  ? t("modules.createDescription")
                  : t("modules.detailsDescription")}
              </p>
            </div>
            <div className="form-grid">
              <div className="rule-field">
                <label htmlFor="module-name">
                  {t("modules.fields.moduleName")}
                </label>
                <input
                  id="module-name"
                  value={draft.module_name}
                  onChange={(event) =>
                    setDraft((prev) => ({
                      ...prev,
                      module_name: event.target.value,
                    }))
                  }
                />
              </div>
              <div className="rule-field">
                <label htmlFor="module-id">
                  {t("modules.fields.moduleId")}
                </label>
                <input
                  id="module-id"
                  value={
                    activeModule?.module_id || t("modules.generatedAfterCreate")
                  }
                  readOnly
                />
              </div>
              <div className="rule-field rule-field-wide">
                <label htmlFor="module-inbound-tags">
                  {t("modules.fields.inboundTags")}
                </label>
                <textarea
                  id="module-inbound-tags"
                  className="note-box"
                  value={draft.inbound_tags}
                  onChange={(event) =>
                    setDraft((prev) => ({
                      ...prev,
                      inbound_tags: event.target.value,
                    }))
                  }
                />
              </div>
            </div>
          </div>

          {modalMode === "detail" && loadingDetail && !detail ? (
            <div className="panel">{t("common.loading")}</div>
          ) : null}

          {modalMode === "detail" && activeModule ? (
            <>
              <div className="detail-grid">
                <div className="panel">
                  <div className="panel-heading">
                    <h2>{t("modules.healthTitle")}</h2>
                    <p className="muted">{t("modules.healthDescription")}</p>
                  </div>
                  <div className="detail-list">
                    <div>
                      <dt>{t("modules.freshnessTitle")}</dt>
                      <dd>{t(heartbeatLabelKey(activeModule))}</dd>
                    </div>
                    <div>
                      <dt>{t("modules.healthStatus")}</dt>
                      <dd>
                        {activeModule.install_state === "pending_install"
                          ? t("modules.pendingInstall")
                          : t(`modules.health.${activeModule.health_status}`)}
                      </dd>
                    </div>
                    <div>
                      <dt>{t("modules.lastHeartbeatAge")}</dt>
                      <dd>{formatAge(activeModule.seconds_since_last_seen)}</dd>
                    </div>
                    <div>
                      <dt>{t("modules.lastValidationAt")}</dt>
                      <dd>
                        {formatDisplayDateTime(
                          activeModule.last_validation_at,
                          t("common.notAvailable"),
                          language,
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt>{t("modules.spoolDepth")}</dt>
                      <dd>{activeModule.spool_depth}</dd>
                    </div>
                    <div>
                      <dt>{t("modules.accessLogExists")}</dt>
                      <dd>
                        {activeModule.access_log_exists
                          ? t("common.yes")
                          : t("common.no")}
                      </dd>
                    </div>
                  </div>
                  {activeModule.error_text ? (
                    <div className="error-box">{activeModule.error_text}</div>
                  ) : null}
                </div>

                <div className="panel">
                  <div className="panel-heading">
                    <h2>Нагрузка и активность</h2>
                    <p className="muted">
                      Последний снимок по серверу и процессам MobGuard.
                    </p>
                  </div>
                  <div className="stats-grid">
                    <div className="stat-card">
                      <span>Онлайн</span>
                      <strong>{activeModule.runtime_metrics?.active_users ?? "—"}</strong>
                    </div>
                    <div className="stat-card">
                      <span>События</span>
                      <strong>{activeModule.runtime_metrics?.recent_events ?? "—"}</strong>
                    </div>
                    <div className="stat-card">
                      <span>CPU</span>
                      <strong>{formatPercent(activeModule.runtime_metrics?.system?.cpu_percent)}</strong>
                    </div>
                    <div className="stat-card">
                      <span>RAM</span>
                      <strong>{formatPercent(activeModule.runtime_metrics?.system?.memory_percent)}</strong>
                    </div>
                  </div>
                  <div className="module-meters">
                    {renderMetricMeter("CPU", activeModule.runtime_metrics?.system?.cpu_percent)}
                    {renderMetricMeter("RAM", activeModule.runtime_metrics?.system?.memory_percent)}
                    {renderMetricMeter("Диск", activeModule.runtime_metrics?.system?.disk_percent, "%", 80, 92)}
                  </div>
                  <div className="record-grid">
                    <div className="record-kv">
                      <strong>Load avg</strong>
                      <span>
                        {activeModule.runtime_metrics?.system?.load_avg_1m !== null &&
                        activeModule.runtime_metrics?.system?.load_avg_1m !== undefined
                          ? `${activeModule.runtime_metrics?.system?.load_avg_1m?.toFixed(2)} / ${activeModule.runtime_metrics?.system?.load_avg_5m?.toFixed(2) ?? "0.00"} / ${activeModule.runtime_metrics?.system?.load_avg_15m?.toFixed(2) ?? "0.00"}`
                          : "—"}
                      </span>
                    </div>
                    <div className="record-kv">
                      <strong>RAM</strong>
                      <span>
                        {formatBytes(activeModule.runtime_metrics?.system?.memory_used_bytes)} / {formatBytes(activeModule.runtime_metrics?.system?.memory_total_bytes)}
                      </span>
                    </div>
                    <div className="record-kv">
                      <strong>Диск</strong>
                      <span>
                        {formatBytes(activeModule.runtime_metrics?.system?.disk_used_bytes)} / {formatBytes(activeModule.runtime_metrics?.system?.disk_total_bytes)}
                      </span>
                    </div>
                    <div className="record-kv">
                      <strong>Uptime</strong>
                      <span>{formatAge(activeModule.runtime_metrics?.system?.uptime_seconds)}</span>
                    </div>
                    <div className="record-kv">
                      <strong>MobGuard CPU</strong>
                      <span>{formatPercent(activeModule.runtime_metrics?.processes?.cpu_percent)}</span>
                    </div>
                    <div className="record-kv">
                      <strong>MobGuard RSS</strong>
                      <span>{formatBytes(activeModule.runtime_metrics?.processes?.rss_bytes)}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="panel">
                <div className="panel-heading panel-heading-row">
                  <div>
                    <h2>Процессы MobGuard</h2>
                    <p className="muted">
                      Найдено процессов: {activeModule.runtime_metrics?.processes?.match_count ?? 0}
                    </p>
                  </div>
                </div>
                <div className="record-list">
                  {(activeModule.runtime_metrics?.processes?.top || []).length ? (
                    activeModule.runtime_metrics?.processes?.top.map((process, index) => (
                      <div className="record-item" key={`${process.pid || "pid"}-${index}`}>
                        <div className="record-main">
                          <span className="record-title">
                            {process.name || "process"} #{process.pid ?? "—"}
                          </span>
                          <span className={`tag ${metricVariant(process.cpu_percent, 50, 80)}`}>
                            CPU {formatPercent(process.cpu_percent)}
                          </span>
                        </div>
                        <div className="record-grid">
                          <div className="record-kv">
                            <strong>RSS</strong>
                            <span>{formatBytes(process.rss_bytes)}</span>
                          </div>
                          <div className="record-kv">
                            <strong>VMS</strong>
                            <span>{formatBytes(process.vms_bytes)}</span>
                          </div>
                          <div className="record-kv">
                            <strong>Команда</strong>
                            <span>{process.cmdline || "—"}</span>
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="provider-empty">Снимок процессов пока не получен</div>
                  )}
                </div>
              </div>

              <div className="panel">
                <div className="panel-heading panel-heading-row">
                  <div>
                    <h2>{t("modules.installTitle")}</h2>
                    <p className="muted">{t("modules.installDescription")}</p>
                  </div>
                  <div className="action-row">
                    <button
                      className="ghost"
                      disabled={!detail?.install.compose_yaml}
                      onClick={() =>
                        copyText(
                          detail?.install.compose_yaml || "",
                          t("modules.composeCopied"),
                        )
                      }
                    >
                      {t("modules.copyCompose")}
                    </button>
                    <button
                      className="ghost"
                      disabled={
                        loadingDetail ||
                        !activeModule?.token_reveal_available ||
                        !canRevealModuleToken
                      }
                      onClick={revealToken}
                    >
                      {t("modules.revealToken")}
                    </button>
                  </div>
                </div>

                <ol className="module-install-steps">
                  <li>{t("modules.installSteps.clone")}</li>
                  <li>{t("modules.installSteps.compose")}</li>
                  <li>{t("modules.installSteps.token")}</li>
                  <li>{t("modules.installSteps.start")}</li>
                </ol>

                {!activeModule?.token_reveal_available ? (
                  <div className="provider-empty">
                    {t("modules.tokenUnavailable")}
                  </div>
                ) : null}

                {revealedToken ? (
                  <div className="settings-group">
                    <div className="panel-heading panel-heading-row">
                      <div>
                        <h3>{t("modules.tokenTitle")}</h3>
                        <p className="muted">{t("modules.tokenDescription")}</p>
                      </div>
                      <button
                        className="ghost"
                        onClick={() =>
                          copyText(revealedToken, t("modules.tokenCopied"))
                        }
                      >
                        {t("modules.copyToken")}
                      </button>
                    </div>
                    <div className="env-field-current">
                      <span className="muted">{t("modules.tokenValue")}</span>
                      <strong>{revealedToken}</strong>
                    </div>
                  </div>
                ) : null}

                <details className="export-section" open>
                  <summary>{t("modules.installTitle")}</summary>
                  <pre className="log-box module-compose-box">
                    {detail?.install.compose_yaml ||
                      t("modules.installPreviewEmpty")}
                  </pre>
                </details>
              </div>
            </>
          ) : null}
        </div>
      </ModalShell>
    </section>
  );
}
