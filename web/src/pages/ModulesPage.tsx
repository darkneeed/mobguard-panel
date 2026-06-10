import { useEffect, useMemo, useState } from "react";
import { Loader2, Cpu, Layers, Activity } from "lucide-react";

import { hasPermission } from "../app/permissions";
import {
  api,
  ModuleDetailResponse,
  ModuleListResponse,
  ModuleProvisioningPayload,
  ModuleRestartResponse,
  ModuleRecord,
  Session,
} from "../api/client";
import { settingsApi } from "../features/settings/api/client";
import { ModalShell } from "../components/ModalShell";
import { useToast } from "../components/ToastProvider";
import { useI18n } from "../localization";
import { useVisibleItems } from "../shared/useVisibleItems";
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

function formatSystemUptime(seconds?: number | null): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) {
    return "—";
  }
  const total = Math.max(Math.round(seconds), 0);
  const d = Math.floor(total / 86400);
  const h = Math.floor((total % 86400) / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;

  const parts = [];
  if (d > 0) parts.push(`${d}D`);
  parts.push(`${h}H`);
  parts.push(`${m}M`);
  parts.push(`${s}S`);
  return parts.join(" ");
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
  const [restartingModuleId, setRestartingModuleId] = useState("");
  const [logsModuleId, setLogsModuleId] = useState<string | null>(null);
  const [moduleLogs, setModuleLogs] = useState<any[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [togglingModuleId, setTogglingModuleId] = useState("");
  const [revealingToken, setRevealingToken] = useState(false);
  
  const [loadingInbounds, setLoadingInbounds] = useState(false);
  const [inboundsError, setInboundsError] = useState("");
  const [availableInbounds, setAvailableInbounds] = useState<any[]>([]);
  const [manualTag, setManualTag] = useState("");
  const [instructionsOpen, setInstructionsOpen] = useState(false);

  const activeModule = modalMode === "detail" ? (detail?.module ?? null) : null;
  const draftDirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(savedDraft),
    [draft, savedDraft],
  );
  const currentTags = useMemo(() => {
    return draft.inbound_tags
      .split(/\r?\n|,/)
      .map((item) => item.trim())
      .filter(Boolean);
  }, [draft.inbound_tags]);

  const uniqueInboundTags = useMemo(() => {
    const tags = availableInbounds.map((item) => item.tag).filter(Boolean);
    return Array.from(new Set([...tags, ...currentTags]));
  }, [availableInbounds, currentTags]);

  const modalOpen = modalMode !== null;
  const canManageModules = hasPermission(session, "modules.write");
  const canRevealModuleToken = hasPermission(session, "modules.token_reveal");
  const canSubmit =
    modalMode === "create"
      ? draftDirty && Boolean(draft.module_name.trim())
      : draftDirty;
  const showStandaloneParams = modalMode === "create" || (activeModule && activeModule.install_state === "pending_install");

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
  const {
    visibleItems: visibleModuleItems,
    hasMore: hasMoreModules,
    loadMoreRef: loadMoreModulesRef,
  } = useVisibleItems(filteredItems, { initialCount: 10, step: 10 });

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
  const modulesOnlineFromItems = useMemo(
    () =>
      (data?.items || []).reduce(
        (total, item) => total + Math.max(Number(item.runtime_metrics?.active_users ?? 0), 0),
        0,
      ),
    [data?.items],
  );

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
    setInstructionsOpen(false);
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
    setInboundsError("");
    setManualTag("");
    setInstructionsOpen(false);
  }

  function closeModal() {
    setModalMode(null);
    setPanelError("");
    setSaved("");
    setRevealedToken("");
    setInboundsError("");
    setManualTag("");
    setInstructionsOpen(false);
  }

  // Automatically fetch Remnawave inbounds when module modal opens or module_name changes
  useEffect(() => {
    if (!modalMode) {
      setAvailableInbounds([]);
      return;
    }

    const fetchInbounds = () => {
      setLoadingInbounds(true);
      setInboundsError("");
      settingsApi.getRemnawaveInbounds(draft.module_name || undefined)
        .then((response) => {
          if (response.available) {
            setAvailableInbounds(response.inbounds || []);
          } else {
            setAvailableInbounds([]);
          }
        })
        .catch((err) => {
          setInboundsError(err instanceof Error ? err.message : "Не удалось загрузить инбаунды");
        })
        .finally(() => {
          setLoadingInbounds(false);
        });
    };

    const delayDebounce = setTimeout(fetchInbounds, 400);
    return () => clearTimeout(delayDebounce);
  }, [modalMode, draft.module_name]);

  // Poll module details automatically every 5s when viewing module details to detect first heartbeat
  useEffect(() => {
    if (modalMode === "detail" && selectedId) {
      const interval = setInterval(async () => {
        try {
          const payload = (await api.getModuleDetail(selectedId)) as ModuleDetailResponse;
          setDetail(payload);
          setSavedDraft(draftFromModule(payload.module));
        } catch (err) {
          console.error("Failed to poll module details:", err);
        }
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [modalMode, selectedId]);

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
    setRevealingToken(true);
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
    } finally {
      setRevealingToken(false);
    }
  }

  async function toggleModule(item: ModuleRecord) {
    if (!canManageModules) return;
    const nextEnabled = !item.enabled;
    setTogglingModuleId(item.module_id);
    try {
      const response = (await api.toggleModuleEnabled(item.module_id, nextEnabled)) as ModuleDetailResponse;
      const updatedModule = response?.module;
      if (updatedModule) {
        setData((prev) =>
          prev
            ? {
                ...prev,
                items: prev.items.map((moduleItem) =>
                  moduleItem.module_id === updatedModule.module_id ? updatedModule : moduleItem,
                ),
              }
            : prev,
        );
        pushToast("success", nextEnabled ? "Модуль успешно включен" : "Модуль успешно выключен");
      }
    } catch (err) {
      pushToast(
        "error",
        err instanceof Error ? err.message : "Не удалось изменить статус модуля",
      );
    } finally {
      setTogglingModuleId("");
    }
  }

  async function viewLogs(moduleId: string) {
    setLogsModuleId(moduleId);
    setLoadingLogs(true);
    setModuleLogs([]);
    try {
      const response = (await api.getConsoleEntries({ module_id: moduleId, page_size: 100 })) as any;
      setModuleLogs(response.items || []);
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "Не удалось загрузить логи модуля");
    } finally {
      setLoadingLogs(false);
    }
  }

  async function restartModule(item: ModuleRecord) {
    if (!canManageModules || item.install_state === "pending_install") return;
    setRestartingModuleId(item.module_id);
    try {
      const response = (await api.restartModule(item.module_id)) as ModuleRestartResponse;
      const updatedModule = response?.module;
      if (updatedModule) {
        setData((prev) =>
          prev
            ? {
                ...prev,
                items: prev.items.map((moduleItem) =>
                  moduleItem.module_id === updatedModule.module_id ? updatedModule : moduleItem,
                ),
              }
            : prev,
        );
        setDetail((prev) =>
          prev && prev.module.module_id === updatedModule.module_id
            ? { ...prev, module: updatedModule }
            : prev,
        );
      }
      pushToast("success", t("modules.restartSuccess"));
    } catch (err) {
      pushToast(
        "error",
        err instanceof Error ? err.message : t("modules.restartFailed"),
      );
    } finally {
      setRestartingModuleId("");
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
    const recentEvents = runtime?.recent_events ?? 0;
    const isModuleEnabled = item.enabled !== false;

    return (
      <article
        className={`queue-card module-ops-card ${isActive ? "module-card-active" : ""}`}
        key={item.module_id}
        style={{ opacity: isModuleEnabled ? 1 : 0.65, display: "flex", flexDirection: "column", gap: "1rem" }}
      >
        <div className="queue-card-top" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
              <strong style={{ fontSize: "1.1rem" }}>{item.module_name}</strong>
              <span className={`status-badge ${isModuleEnabled ? "status-resolved" : "severity-low"}`} style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem" }}>
                {isModuleEnabled ? "Активен" : "Отключен"}
              </span>
              {isModuleEnabled && (
                <span className="status-badge review-only" style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem" }}>
                  Онлайн: {runtime?.active_users ?? 0}
                </span>
              )}
            </div>
            <div className="queue-card-identifiers" style={{ marginTop: "0.25rem", display: "flex", flexDirection: "column", gap: "0.15rem" }}>
              <span>ID: {item.module_id}</span>
              <span>Версия: {item.version || "—"}</span>
            </div>
          </div>
          <div className="queue-card-flags" style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap", justifyContent: "flex-end" }}>
            <span className={`status-badge module-status-pill ${heartbeatVariant(item)}`} style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
              <span className={`status-led ${heartbeatVariant(item)}`} />
              {t(heartbeatLabelKey(item))}
            </span>
            {item.install_state !== "pending_install" ? (
              <span className={`tag module-status-pill ${validationVariant(item)}`} style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
                <span className={`status-led ${validationVariant(item)}`} />
                {t(`modules.health.${item.health_status}`)}
              </span>
            ) : null}
          </div>
        </div>

        <div className="module-toggle-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "var(--surface-soft)", padding: "0.6rem 0.85rem", borderRadius: "8px", border: "1px solid var(--line)" }}>
          <span style={{ fontSize: "0.85rem", fontWeight: 500, color: "var(--muted)" }}>Статус модуля:</span>
          {togglingModuleId === item.module_id ? (
            <Loader2 size={16} className="spinner" />
          ) : (
            <button
              className={isModuleEnabled ? "btn-disable" : "btn-enable"}
              style={{
                padding: "0.35rem 0.85rem",
                fontSize: "0.8rem",
                borderRadius: "6px",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.35rem",
                minWidth: "100px"
              }}
              disabled={!canManageModules}
              onClick={() => toggleModule(item)}
            >
              <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "50%", background: isModuleEnabled ? "var(--danger)" : "var(--success)" }} />
              {isModuleEnabled ? "Отключить" : "Включить"}
            </button>
          )}
        </div>

        <div className="module-ops-grid" style={{ gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
          <div className="module-ops-chip">
            <span>События {runtime?.activity_window_seconds ? `${Math.round(runtime.activity_window_seconds / 60)}м` : ""}</span>
            <strong>{recentEvents}</strong>
          </div>
          <div className="module-ops-chip">
            <span>Spool Depth</span>
            <strong>{item.spool_depth}</strong>
          </div>
        </div>

        {system ? (
          <div className="module-meters" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {renderMetricMeter("CPU модуля", system.cpu_percent)}
            {renderMetricMeter("RAM модуля", system.memory_percent)}
            {renderMetricMeter("Диск модуля", system.disk_percent, "%", 80, 92)}
          </div>
        ) : (
          <div style={{ padding: "0.75rem", background: "var(--surface-soft)", borderRadius: "8px", textAlign: "center", fontSize: "0.85rem", color: "var(--muted)" }}>
            Метрики системы временно недоступны (ожидание heartbeat)
          </div>
        )}

        <div className="module-info-panel" style={{ background: "var(--surface-soft)", border: "1px solid var(--line)", padding: "0.85rem", borderRadius: "10px", display: "flex", flexDirection: "column", gap: "0.6rem", fontSize: "0.85rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span className="muted">{t("modules.lastSeen")}:</span>
            <span style={{ fontWeight: 500 }}>{formatDisplayDateTime(item.last_seen_at, t("common.notAvailable"), language)}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span className="muted">Heartbeat лаг:</span>
            <span style={{ color: item.healthy ? "var(--success)" : "var(--danger)", fontWeight: 600 }}>
              {formatAge(item.seconds_since_last_seen)}
            </span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span className="muted">Лог-файл активен:</span>
            {item.access_log_exists ? (
              <span className="status-badge status-resolved" style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem" }}>Да</span>
            ) : (
              <span className="status-badge severity-low" style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem" }}>Нет</span>
            )}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", borderTop: "1px solid var(--line)", paddingTop: "0.6rem" }}>
            <span className="muted">INBOUND теги:</span>
            {item.inbound_tags.length ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.3rem", marginTop: "0.15rem" }}>
                {item.inbound_tags.map(tag => (
                  <span key={tag} className="tag" style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem", borderRadius: "4px", background: "var(--surface-strong)", border: "1px solid var(--line)", color: "var(--ink)" }}>
                    {tag}
                  </span>
                ))}
              </div>
            ) : (
              <span className="muted">—</span>
            )}
          </div>
        </div>

        {item.error_text ? <div className="error-box" style={{ padding: "0.5rem 0.75rem" }}>{item.error_text}</div> : null}

        <div className="action-row" style={{ display: "flex", gap: "0.5rem", marginTop: "auto", borderTop: "1px solid var(--line)", paddingTop: "1rem" }}>
          <button className="btn-details" style={{ flex: 1.2, padding: "0.5rem" }} onClick={() => openModule(item.module_id)}>
            {t("modules.open")}
          </button>
          <button className="btn-log" style={{ flex: 1, padding: "0.5rem" }} onClick={() => viewLogs(item.module_id)}>
            Лог
          </button>
          <button
            className="btn-restart"
            style={{ flex: 1, padding: "0.5rem", display: "inline-flex", alignItems: "center", justifyContent: "center" }}
            disabled={
              !canManageModules ||
              item.install_state === "pending_install" ||
              restartingModuleId === item.module_id
            }
            onClick={() => restartModule(item)}
          >
            {restartingModuleId === item.module_id ? (
              <Loader2 size={14} className="spinner" />
            ) : (
              "Рестарт"
            )}
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
          {visibleModuleItems.map(renderModuleCard)}
          {hasMoreModules ? (
            <div className="provider-empty muted" ref={loadMoreModulesRef}>
              <span>{t("common.loading")}</span>
            </div>
          ) : null}
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
              style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}
            >
              {submitting && <Loader2 size={14} className="spinner" />}
              {modalMode === "create" ? t("modules.create") : t("modules.save")}
            </button>
          </div>
        }
      >
        {panelError ? <div className="error-box">{panelError}</div> : null}
        {saved ? <div className="ok-box">{saved}</div> : null}

        <div className="modules-modal-stack">
          {showStandaloneParams && (
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
                  <label style={{ display: "block", marginBottom: "0.25rem", fontWeight: 600 }}>
                    {t("modules.fields.inboundTags")}
                  </label>
                  <p className="muted" style={{ fontSize: "0.825rem", marginTop: 0, marginBottom: "0.75rem", color: "var(--muted)" }}>
                    Укажите теги входящих подключений (inbounds) из Remnawave, трафик через которые должен защищаться этим модулем.
                  </p>

                  {loadingInbounds && uniqueInboundTags.length === 0 ? (
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "1rem", background: "var(--surface-soft)", borderRadius: "8px", border: "1px solid var(--line)" }}>
                      <Loader2 size={16} className="spinner" />
                      <span style={{ fontSize: "0.85rem", color: "var(--muted)" }}>Загрузка доступных инбаундов из Remnawave...</span>
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                      {uniqueInboundTags.length > 0 ? (
                        <div style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "0.35rem",
                          maxHeight: "220px",
                          overflowY: "auto",
                          padding: "0.35rem",
                          background: "var(--surface-soft)",
                          borderRadius: "8px",
                          border: "1px solid var(--line)"
                        }}>
                          {uniqueInboundTags.map((tag) => {
                            const isSelected = currentTags.includes(tag);
                            return (
                              <label
                                key={tag}
                                style={{
                                  display: "flex",
                                  alignItems: "flex-start",
                                  gap: "0.6rem",
                                  padding: "0.45rem 0.75rem",
                                  borderRadius: "6px",
                                  background: isSelected ? "rgba(16,185,129,0.06)" : "transparent",
                                  border: isSelected ? "1px solid var(--success)" : "1px solid transparent",
                                  cursor: "pointer",
                                  fontSize: "0.85rem",
                                  userSelect: "none",
                                  transition: "all 0.15s ease",
                                  outline: "none",
                                  width: "100%"
                                }}
                              >
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={() => {
                                    const nextTags = isSelected
                                      ? currentTags.filter((t) => t !== tag)
                                      : [...currentTags, tag];
                                    setDraft((prev) => ({
                                      ...prev,
                                      inbound_tags: nextTags.join("\n")
                                    }));
                                  }}
                                  style={{
                                    marginTop: "0.15rem",
                                    width: "16px",
                                    height: "16px",
                                    padding: 0,
                                    flexShrink: 0,
                                    accentColor: "var(--success)",
                                    cursor: "pointer"
                                  }}
                                />
                                <span style={{
                                  fontWeight: isSelected ? 600 : 400,
                                  color: isSelected ? "var(--success)" : "var(--ink)",
                                  whiteSpace: "normal",
                                  overflowWrap: "break-word",
                                  wordBreak: "break-word",
                                  lineHeight: "1.4",
                                  flex: 1
                                }}>
                                  {tag}
                                </span>
                              </label>
                            );
                          })}
                        </div>
                      ) : (
                        <div style={{ padding: "0.75rem", background: "var(--surface-soft)", borderRadius: "8px", border: "1px solid var(--line)", textAlign: "center", fontSize: "0.85rem", color: "var(--muted)" }}>
                          Нет доступных инбаундов. Добавьте тег вручную ниже.
                        </div>
                      )}

                      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                        <input
                          placeholder="Добавить тег вручную (например: my-custom-inbound)"
                          value={manualTag}
                          onChange={(e) => setManualTag(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              const trimmed = manualTag.trim();
                              if (trimmed) {
                                const nextTags = currentTags.includes(trimmed)
                                  ? currentTags
                                  : [...currentTags, trimmed];
                                setDraft((prev) => ({
                                  ...prev,
                                  inbound_tags: nextTags.join("\n")
                                }));
                                setManualTag("");
                              }
                            }
                          }}
                          style={{ flex: 1, fontSize: "0.85rem", padding: "0.45rem 0.75rem", borderRadius: "6px", border: "1px solid var(--line)", background: "var(--surface-soft)", color: "var(--ink)" }}
                        />
                        <button
                          type="button"
                          onClick={() => {
                            const trimmed = manualTag.trim();
                            if (trimmed) {
                              const nextTags = currentTags.includes(trimmed)
                                ? currentTags
                                : [...currentTags, trimmed];
                              setDraft((prev) => ({
                                ...prev,
                                inbound_tags: nextTags.join("\n")
                              }));
                              setManualTag("");
                            }
                          }}
                          style={{ fontSize: "0.85rem", padding: "0.45rem 0.85rem", borderRadius: "6px", background: "var(--surface-strong)", border: "1px solid var(--line)", cursor: "pointer", color: "var(--ink)" }}
                        >
                          + Добавить
                        </button>
                      </div>
                    </div>
                  )}

                  {inboundsError && (
                    <div className="error-box" style={{ marginTop: "0.5rem", padding: "0.5rem 0.75rem", fontSize: "0.85rem" }}>
                      {inboundsError}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {modalMode === "detail" && loadingDetail && !detail ? (
            <div className="panel">{t("common.loading")}</div>
          ) : null}

          {modalMode === "detail" && activeModule ? (
            (() => {
              const isInstalled = activeModule.install_state !== "pending_install";
              return (
                <>
                  {!isInstalled ? (
                    // SHOW WIZARD STEPPERS AND CONNECTING SCREEN ONLY
                    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                      {/* Step Indicator */}
                      <div className="wizard-steps" style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        position: "relative",
                        padding: "0.5rem 1rem",
                        background: "var(--surface-soft)",
                        borderRadius: "10px",
                        border: "1px solid var(--line)"
                      }}>
                        <div style={{
                          position: "absolute",
                          top: "50%",
                          left: "15%",
                          right: "15%",
                          height: "2px",
                          background: "var(--line)",
                          zIndex: 1
                        }} />
                        <div style={{
                          position: "absolute",
                          top: "50%",
                          left: "15%",
                          width: "35%",
                          height: "2px",
                          background: "var(--success)",
                          zIndex: 1
                        }} />
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", zIndex: 2, gap: "0.25rem" }}>
                          <span style={{
                            width: "24px",
                            height: "24px",
                            borderRadius: "50%",
                            background: "var(--success)",
                            color: "white",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "0.8rem",
                            fontWeight: "bold"
                          }}>✓</span>
                          <span style={{ fontSize: "0.75rem", color: "var(--muted)", fontWeight: 500 }}>1. Создание</span>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", zIndex: 2, gap: "0.25rem" }}>
                          <span style={{
                            width: "24px",
                            height: "24px",
                            borderRadius: "50%",
                            background: "var(--success)",
                            color: "white",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "0.8rem",
                            fontWeight: "bold"
                          }}>2</span>
                          <span style={{ fontSize: "0.75rem", color: "var(--success)", fontWeight: 600 }}>2. Установка</span>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", zIndex: 2, gap: "0.25rem" }}>
                          <span style={{
                            width: "24px",
                            height: "24px",
                            borderRadius: "50%",
                            background: "var(--line)",
                            color: "var(--muted)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "0.8rem",
                            fontWeight: "bold"
                          }}>3</span>
                          <span style={{ fontSize: "0.75rem", color: "var(--muted)", fontWeight: 500 }}>3. Подключение</span>
                        </div>
                      </div>

                      {/* Connecting Pulsating Box */}
                      <div className="connecting-card" style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        padding: "2.5rem 1.5rem",
                        background: "rgba(59,130,246,0.03)",
                        border: "1px solid rgba(59,130,246,0.15)",
                        borderRadius: "12px",
                        textAlign: "center",
                        gap: "1rem"
                      }}>
                        <div className="pulsating-icon" style={{
                          width: "64px",
                          height: "64px",
                          borderRadius: "50%",
                          background: "rgba(59,130,246,0.1)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: "var(--accent)"
                        }}>
                          <Loader2 size={36} className="spinner" style={{ color: "var(--accent)" }} />
                        </div>
                        <div>
                          <strong style={{ fontSize: "1.15rem", display: "block", marginBottom: "0.35rem", color: "var(--accent)" }}>
                            Ожидание heartbeat-сигнала...
                          </strong>
                          <p style={{ fontSize: "0.85rem", color: "var(--muted)", margin: 0, maxWidth: "420px" }}>
                            Установите модуль MobGuard на вашем сервере, используя инструкции и токен ниже. Как только поступит первый отчет активности, откроются детали.
                          </p>
                        </div>
                      </div>

                      {/* Installation instructions panel */}
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
                                revealingToken ||
                                !activeModule?.token_reveal_available ||
                                !canRevealModuleToken
                              }
                              onClick={revealToken}
                              style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}
                            >
                              {revealingToken && <Loader2 size={14} className="spinner" />}
                              {t("modules.revealToken")}
                            </button>
                          </div>
                        </div>

                        <ol className="module-install-steps" style={{ paddingLeft: "1.25rem", margin: "1rem 0" }}>
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
                          <div className="settings-group" style={{ marginTop: "1rem" }}>
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

                        <details className="export-section" open style={{ marginTop: "1.5rem" }}>
                          <summary>{t("modules.installTitle")}</summary>
                          <pre className="log-box module-compose-box">
                            {detail?.install.compose_yaml ||
                              t("modules.installPreviewEmpty")}
                          </pre>
                        </details>
                      </div>
                    </div>
                  ) : (
                    // SHOW STATS, DETAILS & PROCESSES (INSTALLED VIEW)
                    <>
                      <div className="modules-dashboard-layout" style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
                        gap: "1.25rem",
                        marginTop: "1rem",
                        alignItems: "start"
                      }}>
                        {/* LEFT COLUMN */}
                        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                          
                          {/* CARD 1: ДЕТАЛИ МОДУЛЯ */}
                          <div className="panel" style={{ margin: 0, padding: "1.25rem" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <Activity size={18} style={{ color: "var(--success)" }} />
                                <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>Детали модуля</h3>
                              </div>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <span className={`status-badge module-status-pill ${heartbeatVariant(activeModule)}`} style={{ fontSize: "0.72rem", padding: "0.2rem 0.5rem", display: "inline-flex", alignItems: "center", gap: "0.3rem" }}>
                                  <span className={`status-led ${heartbeatVariant(activeModule)}`} style={{ width: "6px", height: "6px" }} />
                                  {t(heartbeatLabelKey(activeModule))}
                                </span>
                                <button
                                  className="ghost"
                                  style={{ padding: "0.25rem", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", minWidth: 0, width: "28px", height: "28px", border: "1px solid var(--line)" }}
                                  disabled={!canManageModules || restartingModuleId === activeModule.module_id}
                                  onClick={() => restartModule(activeModule)}
                                  title="Перезапустить модуль"
                                >
                                  {restartingModuleId === activeModule.module_id ? (
                                    <Loader2 size={12} className="spinner" />
                                  ) : (
                                    <span style={{ fontSize: "0.75rem" }}>🔄</span>
                                  )}
                                </button>
                              </div>
                            </div>

                            <div style={{ marginBottom: "1rem" }}>
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "0.25rem" }}>
                                <span style={{ fontSize: "1.25rem", fontWeight: 700 }}>
                                  {activeModule.runtime_metrics?.recent_events ?? 0} событий
                                </span>
                                <span style={{ fontSize: "0.85rem", color: "var(--muted)" }}>∞</span>
                              </div>
                              <div style={{ height: "4px", background: "var(--success)", borderRadius: "2px" }} />
                            </div>

                            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem" }}>
                              <div style={{
                                background: "var(--surface-soft)",
                                border: "1px solid var(--line)",
                                borderRadius: "8px",
                                padding: "0.5rem",
                                textAlign: "center",
                                fontSize: "0.78rem",
                                display: "flex",
                                flexDirection: "column",
                                alignItems: "center",
                                gap: "0.2rem"
                              }}>
                                <span style={{ color: "var(--muted)", fontSize: "0.7rem", textTransform: "uppercase" }}>Онлайн</span>
                                <strong style={{ fontSize: "0.9rem" }}>👥 {activeModule.runtime_metrics?.active_users ?? 0}</strong>
                              </div>
                              <div style={{
                                background: "var(--surface-soft)",
                                border: "1px solid var(--line)",
                                borderRadius: "8px",
                                padding: "0.5rem",
                                textAlign: "center",
                                fontSize: "0.78rem",
                                display: "flex",
                                flexDirection: "column",
                                alignItems: "center",
                                gap: "0.2rem"
                              }}>
                                <span style={{ color: "var(--muted)", fontSize: "0.7rem", textTransform: "uppercase" }}>Версия</span>
                                <strong style={{ fontSize: "0.9rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "100%" }}>
                                  ✦ {activeModule.version || "—"}
                                </strong>
                              </div>
                              <div style={{
                                background: "var(--surface-soft)",
                                border: "1px solid var(--line)",
                                borderRadius: "8px",
                                padding: "0.5rem",
                                textAlign: "center",
                                fontSize: "0.78rem",
                                display: "flex",
                                flexDirection: "column",
                                alignItems: "center",
                                gap: "0.2rem"
                              }}>
                                <span style={{ color: "var(--muted)", fontSize: "0.7rem", textTransform: "uppercase" }}>Лог-файл</span>
                                <strong style={{
                                  fontSize: "0.82rem",
                                  color: activeModule.access_log_exists ? "var(--success)" : "var(--muted)"
                                }}>
                                  {activeModule.access_log_exists ? "АКТИВЕН" : "НЕТ"}
                                </strong>
                              </div>
                            </div>

                            {activeModule.error_text && (
                              <div className="error-box" style={{ marginTop: "0.75rem", padding: "0.5rem 0.75rem", fontSize: "0.8rem", margin: "0.75rem 0 0" }}>
                                {activeModule.error_text}
                              </div>
                            )}
                          </div>

                          {/* CARD 2: ПАРАМЕТРЫ МОДУЛЯ */}
                          <div className="panel" style={{ margin: 0, padding: "1.25rem" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem" }}>
                              <span style={{ fontSize: "1.1rem" }}>📇</span>
                              <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>Параметры модуля</h3>
                            </div>

                            <div className="rule-field" style={{ marginBottom: "0.75rem" }}>
                              <label htmlFor="module-name-dash" style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: "0.25rem" }}>
                                Имя модуля *
                              </label>
                              <div style={{ position: "relative" }}>
                                <span style={{ position: "absolute", left: "0.75rem", top: "50%", transform: "translateY(-50%)", fontSize: "0.9rem", color: "var(--muted)" }}>🛡️</span>
                                <input
                                  id="module-name-dash"
                                  value={draft.module_name}
                                  onChange={(event) =>
                                    setDraft((prev) => ({
                                      ...prev,
                                      module_name: event.target.value,
                                    }))
                                  }
                                  style={{ paddingLeft: "2.25rem", width: "100%", fontSize: "0.85rem" }}
                                />
                              </div>
                            </div>

                            <div className="rule-field" style={{ marginBottom: "0.75rem" }}>
                              <label htmlFor="module-id-dash" style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: "0.25rem" }}>
                                Идентификатор модуля
                              </label>
                              <div style={{ position: "relative" }}>
                                <span style={{ position: "absolute", left: "0.75rem", top: "50%", transform: "translateY(-50%)", fontSize: "0.9rem", color: "var(--muted)" }}>🆔</span>
                                <input
                                  id="module-id-dash"
                                  value={activeModule.module_id}
                                  readOnly
                                  style={{ paddingLeft: "2.25rem", width: "100%", fontSize: "0.85rem", background: "rgba(255,255,255,0.02)", color: "var(--muted)", cursor: "not-allowed" }}
                                />
                              </div>
                            </div>

                            <div className="rule-field" style={{ marginBottom: "0.5rem" }}>
                              <label style={{ fontSize: "0.8rem", color: "var(--muted)", fontWeight: 600, marginBottom: "0.15rem" }}>
                                INBOUND теги Remnawave
                              </label>
                              <p className="muted" style={{ fontSize: "0.75rem", marginTop: 0, marginBottom: "0.5rem", color: "var(--muted)", lineHeight: "1.4" }}>
                                Выберите inbounds для защиты трафика или добавьте теги вручную.
                              </p>

                              {loadingInbounds && uniqueInboundTags.length === 0 ? (
                                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.75rem", background: "rgba(255,255,255,0.02)", borderRadius: "8px", border: "1px solid var(--line)" }}>
                                  <Loader2 size={14} className="spinner" />
                                  <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>Загрузка инбаундов...</span>
                                </div>
                              ) : (
                                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                                  {uniqueInboundTags.length > 0 ? (
                                    <div style={{
                                      display: "flex",
                                      flexDirection: "column",
                                      gap: "0.35rem",
                                      maxHeight: "150px",
                                      overflowY: "auto",
                                      padding: "0.35rem",
                                      background: "rgba(0,0,0,0.15)",
                                      borderRadius: "8px",
                                      border: "1px solid var(--line)"
                                    }}>
                                      {uniqueInboundTags.map((tag) => {
                                        const isSelected = currentTags.includes(tag);
                                        return (
                                          <label
                                            key={tag}
                                            style={{
                                              display: "flex",
                                              alignItems: "flex-start",
                                              gap: "0.5rem",
                                              padding: "0.40rem 0.65rem",
                                              borderRadius: "6px",
                                              background: isSelected ? "rgba(52,211,153,0.05)" : "transparent",
                                              border: isSelected ? "1px solid rgba(52,211,153,0.3)" : "1px solid transparent",
                                              cursor: "pointer",
                                              fontSize: "0.80rem",
                                              userSelect: "none",
                                              transition: "all 0.15s ease",
                                              width: "100%"
                                            }}
                                          >
                                            <input
                                              type="checkbox"
                                              checked={isSelected}
                                              onChange={() => {
                                                const nextTags = isSelected
                                                  ? currentTags.filter((t) => t !== tag)
                                                  : [...currentTags, tag];
                                                setDraft((prev) => ({
                                                  ...prev,
                                                  inbound_tags: nextTags.join("\n")
                                                }));
                                              }}
                                              style={{
                                                marginTop: "0.15rem",
                                                width: "16px",
                                                height: "16px",
                                                padding: 0,
                                                flexShrink: 0,
                                                accentColor: "var(--success)",
                                                cursor: "pointer"
                                              }}
                                            />
                                            <span style={{
                                              fontWeight: isSelected ? 600 : 400,
                                              color: isSelected ? "var(--success)" : "var(--ink)",
                                              whiteSpace: "normal",
                                              overflowWrap: "break-word",
                                              wordBreak: "break-word",
                                              lineHeight: "1.4",
                                              flex: 1
                                              }}
                                            >
                                              {tag}
                                            </span>
                                          </label>
                                        );
                                      })}
                                    </div>
                                  ) : (
                                    <div style={{ padding: "0.5rem", background: "rgba(0,0,0,0.15)", borderRadius: "8px", border: "1px solid var(--line)", textAlign: "center", fontSize: "0.78rem", color: "var(--muted)" }}>
                                      Нет доступных инбаундов. Добавьте вручную.
                                    </div>
                                  )}

                                  <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
                                    <input
                                      placeholder="Добавить тег вручную..."
                                      value={manualTag}
                                      onChange={(e) => setManualTag(e.target.value)}
                                      onKeyDown={(e) => {
                                        if (e.key === "Enter") {
                                          e.preventDefault();
                                          const trimmed = manualTag.trim();
                                          if (trimmed) {
                                            const nextTags = currentTags.includes(trimmed)
                                              ? currentTags
                                              : [...currentTags, trimmed];
                                            setDraft((prev) => ({
                                              ...prev,
                                              inbound_tags: nextTags.join("\n")
                                            }));
                                            setManualTag("");
                                          }
                                        }
                                      }}
                                      style={{ flex: 1, fontSize: "0.78rem", padding: "0.35rem 0.5rem", borderRadius: "6px", border: "1px solid var(--line)", background: "rgba(0,0,0,0.15)", color: "var(--ink)" }}
                                    />
                                    <button
                                      type="button"
                                      onClick={() => {
                                        const trimmed = manualTag.trim();
                                        if (trimmed) {
                                          const nextTags = currentTags.includes(trimmed)
                                            ? currentTags
                                            : [...currentTags, trimmed];
                                          setDraft((prev) => ({
                                            ...prev,
                                            inbound_tags: nextTags.join("\n")
                                          }));
                                          setManualTag("");
                                        }
                                      }}
                                      style={{ fontSize: "0.78rem", padding: "0.35rem 0.65rem", borderRadius: "6px", background: "var(--surface-strong)", border: "1px solid var(--line)", cursor: "pointer", color: "var(--ink)" }}
                                    >
                                      + Добавить
                                    </button>
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>

                        </div>

                        {/* RIGHT COLUMN */}
                        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                          
                          {/* CARD 3: СИСТЕМА */}
                          <div className="panel" style={{ margin: 0, padding: "1.25rem" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <Cpu size={18} style={{ color: "var(--accent)" }} />
                                <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>Система</h3>
                                <span className="status-badge" style={{
                                  fontSize: "0.68rem",
                                  padding: "0.1rem 0.35rem",
                                  background: "rgba(139, 92, 246, 0.12)",
                                  color: "#a78bfa",
                                  border: "1px solid rgba(139, 92, 246, 0.25)",
                                  fontWeight: "bold"
                                }}>
                                  LINUX / X64
                                </span>
                              </div>
                              <span style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--success)" }}>
                                {formatSystemUptime(activeModule.runtime_metrics?.system?.uptime_seconds)}
                              </span>
                            </div>

                            {activeModule.runtime_metrics?.system ? (
                              <>
                                <div style={{ marginBottom: "1.25rem" }}>
                                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem", color: "var(--muted)", textTransform: "uppercase", marginBottom: "0.35rem" }}>
                                    <span>Память</span>
                                    <strong>
                                      {formatBytes(activeModule.runtime_metrics.system.memory_used_bytes)} / {formatBytes(activeModule.runtime_metrics.system.memory_total_bytes)} ({formatPercent(activeModule.runtime_metrics.system.memory_percent)})
                                    </strong>
                                  </div>
                                  <div style={{ height: "6px", background: "rgba(255,255,255,0.06)", borderRadius: "3px", overflow: "hidden" }}>
                                    <div
                                      style={{
                                        height: "100%",
                                        width: meterWidth(activeModule.runtime_metrics.system.memory_percent),
                                        background: "linear-gradient(90deg, var(--accent) 0%, var(--success) 100%)",
                                        borderRadius: "inherit"
                                      }}
                                    />
                                  </div>
                                </div>

                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "1.25rem", background: "rgba(0,0,0,0.12)", padding: "0.6rem 0.8rem", borderRadius: "8px", border: "1px solid var(--line)" }}>
                                  <div>
                                    <span style={{ fontSize: "0.7rem", color: "var(--muted)", textTransform: "uppercase", display: "block", marginBottom: "0.15rem" }}>ДИСК READ</span>
                                    <span style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--ink)", display: "flex", alignItems: "center", gap: "0.25rem" }}>
                                      ↓ {formatRate(activeModule.runtime_metrics.system.disk_read_bps)}
                                    </span>
                                  </div>
                                  <div>
                                    <span style={{ fontSize: "0.7rem", color: "var(--muted)", textTransform: "uppercase", display: "block", marginBottom: "0.15rem" }}>ДИСК WRITE</span>
                                    <span style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--ink)", display: "flex", alignItems: "center", gap: "0.25rem" }}>
                                      ↑ {formatRate(activeModule.runtime_metrics.system.disk_write_bps)}
                                    </span>
                                  </div>
                                </div>

                                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.8rem" }}>
                                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--line)", paddingBottom: "0.4rem" }}>
                                    <span className="muted">Спецификация CPU:</span>
                                    <strong style={{ color: "var(--ink)" }}>
                                      {activeModule.runtime_metrics.system.cpu_cores ? `${activeModule.runtime_metrics.system.cpu_cores} x CPU Cores` : "—"}
                                    </strong>
                                  </div>
                                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--line)", paddingBottom: "0.4rem" }}>
                                    <span className="muted">Загрузка системы (Load Avg):</span>
                                    <strong style={{ color: "var(--ink)" }}>
                                      {activeModule.runtime_metrics.system.load_avg_1m !== null && activeModule.runtime_metrics.system.load_avg_1m !== undefined
                                        ? `${activeModule.runtime_metrics.system.load_avg_1m.toFixed(2)} / ${activeModule.runtime_metrics.system.load_avg_5m?.toFixed(2) ?? "0.00"} / ${activeModule.runtime_metrics.system.load_avg_15m?.toFixed(2) ?? "0.00"}`
                                        : "—"}
                                    </strong>
                                  </div>
                                  <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--line)", paddingBottom: "0.4rem" }}>
                                    <span className="muted">Диск (Системный):</span>
                                    <strong style={{ color: "var(--ink)" }}>
                                      {formatBytes(activeModule.runtime_metrics.system.disk_used_bytes)} / {formatBytes(activeModule.runtime_metrics.system.disk_total_bytes)} ({formatPercent(activeModule.runtime_metrics.system.disk_percent)})
                                    </strong>
                                  </div>
                                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                                    <span className="muted">MobGuard CPU / RSS:</span>
                                    <strong style={{ color: "var(--ink)" }}>
                                      {formatPercent(activeModule.runtime_metrics.processes?.cpu_percent)} / {formatBytes(activeModule.runtime_metrics.processes?.rss_bytes)}
                                    </strong>
                                  </div>
                                </div>
                              </>
                            ) : (
                              <div style={{ padding: "1rem", background: "rgba(0,0,0,0.12)", borderRadius: "8px", textAlign: "center", fontSize: "0.8rem", color: "var(--muted)" }}>
                                Метрики системы временно недоступны
                              </div>
                            )}
                          </div>

                          {/* CARD 4: ПРОЦЕССЫ MOBGUARD */}
                          <div className="panel" style={{ margin: 0, padding: "1.25rem" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <Layers size={18} style={{ color: "var(--success)" }} />
                                <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>Процессы MobGuard</h3>
                              </div>
                              <span style={{ fontSize: "0.75rem", padding: "0.15rem 0.45rem", background: "var(--surface-soft)", borderRadius: "6px", border: "1px solid var(--line)" }}>
                                Найдено: {activeModule.runtime_metrics?.processes?.match_count ?? 0}
                              </span>
                            </div>

                            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", maxHeight: "155px", overflowY: "auto", paddingRight: "0.25rem" }}>
                              {activeModule.runtime_metrics?.processes?.top && activeModule.runtime_metrics.processes.top.length ? (
                                activeModule.runtime_metrics.processes.top.map((process, index) => (
                                  <div
                                    key={`${process.pid || "pid"}-${index}`}
                                    style={{
                                      background: "rgba(0,0,0,0.15)",
                                      border: "1px solid var(--line)",
                                      borderRadius: "8px",
                                      padding: "0.5rem 0.75rem",
                                      fontSize: "0.78rem",
                                      display: "flex",
                                      flexDirection: "column",
                                      gap: "0.3rem"
                                    }}
                                  >
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                      <strong style={{ color: "var(--ink)", fontFamily: "var(--font-mono)" }}>
                                        {process.name || "process"} <span style={{ color: "var(--muted)", fontWeight: "normal" }}>#{process.pid ?? "—"}</span>
                                      </strong>
                                      <span className={`tag ${metricVariant(process.cpu_percent, 50, 80)}`} style={{ padding: "0.1rem 0.35rem", fontSize: "0.7rem" }}>
                                        CPU {formatPercent(process.cpu_percent)}
                                      </span>
                                    </div>
                                    <div style={{ display: "flex", gap: "1rem", fontSize: "0.75rem", color: "var(--muted)", overflow: "hidden" }}>
                                      <span>RSS: <strong style={{ color: "var(--ink)" }}>{formatBytes(process.rss_bytes)}</strong></span>
                                      <span>VMS: <strong style={{ color: "var(--ink)" }}>{formatBytes(process.vms_bytes)}</strong></span>
                                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }} title={process.cmdline || ""}>
                                        Cmd: <strong style={{ color: "var(--ink)" }}>{process.cmdline || "—"}</strong>
                                      </span>
                                    </div>
                                  </div>
                                ))
                              ) : (
                                <div style={{ padding: "1rem", background: "rgba(0,0,0,0.12)", borderRadius: "8px", border: "1px dashed var(--line)", textAlign: "center", fontSize: "0.78rem", color: "var(--muted)" }}>
                                  Снимок процессов пока не получен
                                </div>
                              )}
                            </div>
                          </div>

                        </div>
                      </div>

                      {/* Collapsed Deployment / Installation options for active module */}
                      <details
                        className="panel"
                        open={instructionsOpen}
                        onToggle={(e) => setInstructionsOpen((e.target as HTMLDetailsElement).open)}
                        style={{
                          marginTop: "1.25rem",
                          padding: "1.25rem",
                          background: "var(--bg-panel)",
                          borderRadius: "var(--radius-lg)",
                          border: "1px solid var(--line)",
                          boxShadow: "var(--shadow)"
                        }}
                      >
                        <summary style={{
                          fontWeight: 600,
                          cursor: "pointer",
                          marginBottom: instructionsOpen ? "1rem" : 0,
                          outline: "none",
                          userSelect: "none"
                        }}>
                          Инструкция по установке & Docker Compose YAML
                        </summary>
                        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                          <div className="action-row" style={{ justifyContent: "flex-end" }}>
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
                                revealingToken ||
                                !activeModule?.token_reveal_available ||
                                !canRevealModuleToken
                              }
                              onClick={revealToken}
                              style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}
                            >
                              {revealingToken && <Loader2 size={14} className="spinner" />}
                              {t("modules.revealToken")}
                            </button>
                          </div>
                          
                          <ol className="module-install-steps" style={{ paddingLeft: "1.25rem" }}>
                            <li>{t("modules.installSteps.clone")}</li>
                            <li>{t("modules.installSteps.compose")}</li>
                            <li>{t("modules.installSteps.token")}</li>
                            <li>{t("modules.installSteps.start")}</li>
                          </ol>

                          {revealedToken && (
                            <div className="settings-group">
                              <div className="env-field-current">
                                <span className="muted">{t("modules.tokenValue")}</span>
                                <strong>{revealedToken}</strong>
                              </div>
                            </div>
                          )}

                          <pre className="log-box module-compose-box" style={{ maxHeight: "250px", overflowY: "auto" }}>
                            {detail?.install.compose_yaml || t("modules.installPreviewEmpty")}
                          </pre>
                        </div>
                      </details>
                    </>
                  )}
                </>
              );
            })()
          ) : null}
        </div>
      </ModalShell>

      <ModalShell
        open={logsModuleId !== null}
        onClose={() => setLogsModuleId(null)}
        title={`Системный лог модуля: ${logsModuleId}`}
        description="Последние 100 событий и отчетов от модуля аналитики"
        closeLabel="Закрыть"
      >
        <div className="log-viewer-modal-content" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {loadingLogs ? (
            <div className="provider-empty" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.5rem" }}>
              <Loader2 size={24} className="spinner" />
              <span>Загрузка логов...</span>
            </div>
          ) : moduleLogs.length ? (
            <pre className="log-box code-editor-box" style={{ maxHeight: "450px", overflowY: "auto", fontSize: "0.8rem", padding: "1rem", background: "#0f172a", color: "#e2e8f0", border: "1px solid #334155", borderRadius: "8px" }}>
              {moduleLogs.map((entry: any) => {
                const date = formatDisplayDateTime(entry.timestamp, "—", language);
                const levelColor = entry.level === "error" ? "#f43f5e" : entry.level === "warn" ? "#fbbf24" : "#10b981";
                return (
                  <div key={entry.id} style={{ marginBottom: "0.4rem", display: "flex", gap: "0.5rem", fontFamily: "var(--font-mono)", lineHeight: "1.4" }}>
                    <span style={{ color: "#64748b", flexShrink: 0 }}>[{date}]</span>
                    <span style={{ color: levelColor, fontWeight: "bold", flexShrink: 0, textTransform: "uppercase" }}>[{entry.level}]</span>
                    <span style={{ wordBreak: "break-all", whiteSpace: "pre-wrap" }}>{entry.message}</span>
                  </div>
                );
              })}
            </pre>
          ) : (
            <div className="provider-empty">Логи для этого модуля отсутствуют или модуль еще не передавал события.</div>
          )}
        </div>
      </ModalShell>
    </section>
  );
}
