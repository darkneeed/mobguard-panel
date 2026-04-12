import { useEffect, useMemo, useState } from "react";

import {
  api,
  ModuleDetailResponse,
  ModuleListResponse,
  ModuleProvisioningPayload,
  ModuleRecord
} from "../api/client";
import { useToast } from "../components/ToastProvider";
import { useI18n } from "../localization";
import { formatDisplayDateTime } from "../utils/datetime";

type ModuleDraft = {
  module_name: string;
  host: string;
  port: string;
  access_log_path: string;
  config_profiles: string;
  provider: string;
  notes: string;
};

const EMPTY_DRAFT: ModuleDraft = {
  module_name: "",
  host: "",
  port: "2222",
  access_log_path: "/var/log/remnanode/access.log",
  config_profiles: "Default-Profile",
  provider: "",
  notes: ""
};

function draftFromModule(module: ModuleRecord): ModuleDraft {
  return {
    module_name: module.module_name || "",
    host: module.host || "",
    port: String(module.port || 2222),
    access_log_path: module.access_log_path || "/var/log/remnanode/access.log",
    config_profiles: (module.config_profiles || []).join("\n"),
    provider: module.provider || "",
    notes: module.notes || ""
  };
}

function toProvisioningPayload(draft: ModuleDraft): ModuleProvisioningPayload {
  const port = Number(draft.port);
  if (!Number.isFinite(port)) {
    throw new Error("Port must be a number");
  }
  return {
    module_name: draft.module_name.trim(),
    host: draft.host.trim(),
    port,
    access_log_path: draft.access_log_path.trim(),
    config_profiles: draft.config_profiles
      .split(/\r?\n|,/)
      .map((item) => item.trim())
      .filter(Boolean),
    provider: draft.provider.trim(),
    notes: draft.notes.trim()
  };
}

function statusVariant(module: ModuleRecord): string {
  if (module.install_state === "pending_install") {
    return "review-only";
  }
  return module.healthy ? "status-resolved" : "severity-high";
}

export function ModulesPage() {
  const { t, language } = useI18n();
  const { pushToast } = useToast();
  const [data, setData] = useState<ModuleListResponse | null>(null);
  const [detail, setDetail] = useState<ModuleDetailResponse | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [mode, setMode] = useState<"create" | "detail">("create");
  const [draft, setDraft] = useState<ModuleDraft>(EMPTY_DRAFT);
  const [savedDraft, setSavedDraft] = useState<ModuleDraft>(EMPTY_DRAFT);
  const [revealedToken, setRevealedToken] = useState("");
  const [error, setError] = useState("");
  const [panelError, setPanelError] = useState("");
  const [saved, setSaved] = useState("");
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const activeModule = detail?.module ?? null;
  const draftDirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(savedDraft),
    [draft, savedDraft]
  );

  useEffect(() => {
    let cancelled = false;

    async function loadInitialState() {
      try {
        const listPayload = (await api.getModules()) as ModuleListResponse;
        if (cancelled) return;
        setData(listPayload);
        setError("");

        if (!listPayload.items.length) {
          setMode("create");
          setSelectedId("");
          setDetail(null);
          setDraft(EMPTY_DRAFT);
          setSavedDraft(EMPTY_DRAFT);
          return;
        }

        const targetId = selectedId && listPayload.items.some((item) => item.module_id === selectedId)
          ? selectedId
          : listPayload.items[0].module_id;
        setSelectedId(targetId);
        setMode("detail");
        setLoadingDetail(true);
        const detailPayload = (await api.getModuleDetail(targetId)) as ModuleDetailResponse;
        if (cancelled) return;
        setDetail(detailPayload);
        const normalizedDraft = draftFromModule(detailPayload.module);
        setDraft(normalizedDraft);
        setSavedDraft(normalizedDraft);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("modules.loadFailed"));
        }
      } finally {
        if (!cancelled) {
          setLoadingDetail(false);
        }
      }
    }

    loadInitialState();
    return () => {
      cancelled = true;
    };
  }, [t]);

  async function openModule(moduleId: string) {
    setMode("detail");
    setSelectedId(moduleId);
    setPanelError("");
    setSaved("");
    setRevealedToken("");
    setLoadingDetail(true);
    try {
      const payload = (await api.getModuleDetail(moduleId)) as ModuleDetailResponse;
      setDetail(payload);
      const normalizedDraft = draftFromModule(payload.module);
      setDraft(normalizedDraft);
      setSavedDraft(normalizedDraft);
    } catch (err) {
      setPanelError(err instanceof Error ? err.message : t("modules.loadFailed"));
    } finally {
      setLoadingDetail(false);
    }
  }

  function startCreateFlow() {
    setMode("create");
    setSelectedId("");
    setDetail(null);
    setDraft(EMPTY_DRAFT);
    setSavedDraft(EMPTY_DRAFT);
    setRevealedToken("");
    setPanelError("");
    setSaved("");
  }

  async function saveModule() {
    setSubmitting(true);
    setPanelError("");
    setSaved("");
    try {
      const payload = toProvisioningPayload(draft);
      if (mode === "create") {
        const response = (await api.createModule(payload)) as ModuleDetailResponse;
        const nextDraft = draftFromModule(response.module);
        setMode("detail");
        setSelectedId(response.module.module_id);
        setDetail(response);
        setDraft(nextDraft);
        setSavedDraft(nextDraft);
        setRevealedToken(response.install.module_token || "");
        setData((prev) => {
          const nextItems = [response.module, ...(prev?.items || []).filter((item) => item.module_id !== response.module.module_id)];
          return { items: nextItems, count: nextItems.length };
        });
        setSaved(t("modules.createSuccess"));
      } else if (selectedId) {
        const response = (await api.updateModule(selectedId, payload)) as ModuleDetailResponse;
        const nextDraft = draftFromModule(response.module);
        setDetail(response);
        setDraft(nextDraft);
        setSavedDraft(nextDraft);
        setData((prev) => ({
          items: (prev?.items || []).map((item) => (item.module_id === response.module.module_id ? response.module : item)),
          count: prev?.count || 0
        }));
        setSaved(t("modules.updateSuccess"));
      }
    } catch (err) {
      setPanelError(err instanceof Error ? err.message : t("modules.saveFailed"));
    } finally {
      setSubmitting(false);
    }
  }

  async function revealToken() {
    if (!selectedId) return;
    try {
      const response = (await api.revealModuleToken(selectedId)) as { module_token: string };
      setRevealedToken(response.module_token || "");
      pushToast("success", t("modules.tokenRevealSuccess"));
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : t("modules.tokenRevealFailed"));
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

  function renderModuleCard(item: ModuleRecord) {
    const isActive = mode === "detail" && selectedId === item.module_id;
    const statusKey =
      item.install_state === "pending_install"
        ? "modules.pendingInstall"
        : item.healthy
          ? "modules.online"
          : "modules.stale";

    return (
      <article
        className={`queue-card module-card ${isActive ? "module-card-active" : ""}`}
        key={item.module_id}
      >
        <div className="queue-card-top">
          <strong>{item.module_name}</strong>
          <span className={`status-badge ${statusVariant(item)}`}>{t(statusKey)}</span>
        </div>
        <div className="queue-card-identifiers">
          <span>{t("modules.moduleId", { value: item.module_id })}</span>
          <span>{t("modules.host", { value: item.host || t("common.notAvailable") })}</span>
          <span>{t("modules.port", { value: item.port || t("common.notAvailable") })}</span>
        </div>
        <div className="queue-card-stack">
          <div className="queue-card-meta">
            <span>{t("modules.lastSeen")}</span>
            <strong>{formatDisplayDateTime(item.last_seen_at, t("common.notAvailable"), language)}</strong>
          </div>
          <div className="queue-card-meta">
            <span>{t("modules.configProfiles")}</span>
            <strong>{item.config_profiles?.length ? item.config_profiles.join(", ") : t("common.notAvailable")}</strong>
          </div>
          <div className="queue-card-meta">
            <span>{t("modules.openCases")}</span>
            <strong>{item.open_review_cases ?? 0}</strong>
          </div>
          <div className="queue-card-meta">
            <span>{t("modules.analysisEvents")}</span>
            <strong>{item.analysis_events_count ?? 0}</strong>
          </div>
        </div>
        <div className="action-row">
          <button className="ghost" onClick={() => openModule(item.module_id)}>
            {t("modules.open")}
          </button>
        </div>
      </article>
    );
  }

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <span className="eyebrow">{t("modules.eyebrow")}</span>
          <h1>{t("modules.title")}</h1>
          <p className="page-lede">{t("modules.description")}</p>
        </div>
        <div className="action-row">
          <span className="chip">{t("modules.count", { count: data?.count ?? 0 })}</span>
          <button onClick={startCreateFlow}>{t("modules.create")}</button>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="stats-grid">
        <div className="stat-card">
          <span>{t("modules.cards.total")}</span>
          <strong>{data?.count ?? "—"}</strong>
        </div>
        <div className="stat-card">
          <span>{t("modules.cards.pending")}</span>
          <strong>{data ? data.items.filter((item) => item.install_state === "pending_install").length : "—"}</strong>
        </div>
        <div className="stat-card">
          <span>{t("modules.cards.online")}</span>
          <strong>{data ? data.items.filter((item) => item.install_state !== "pending_install" && item.healthy).length : "—"}</strong>
        </div>
        <div className="stat-card">
          <span>{t("modules.cards.stale")}</span>
          <strong>{data ? data.items.filter((item) => item.install_state !== "pending_install" && !item.healthy).length : "—"}</strong>
        </div>
      </div>

      <div className="detail-layout">
        <div className="detail-main">
          <div className="panel">
            <div className="panel-heading panel-heading-row">
              <div>
                <h2>{t("modules.listTitle")}</h2>
                <p className="muted">{t("modules.listDescription")}</p>
              </div>
              <span className="tag severity-low">{t("modules.selectionHint")}</span>
            </div>
            <div className="queue-grid">
              {(data?.items || []).map(renderModuleCard)}
              {!data?.items.length ? (
                <div className="provider-empty">{t("modules.empty")}</div>
              ) : null}
            </div>
          </div>
        </div>

        <aside className="detail-sidebar">
          <div className="panel">
            <div className="panel-heading panel-heading-row">
              <div>
                <h2>{mode === "create" ? t("modules.createTitle") : t("modules.detailsTitle")}</h2>
                <p className="muted">
                  {mode === "create" ? t("modules.createDescription") : t("modules.detailsDescription")}
                </p>
              </div>
              <div className="action-row">
                <span className={draftDirty ? "tag review-only" : "tag severity-low"}>
                  {draftDirty ? t("common.unsavedChanges") : t("common.saved")}
                </span>
                <button onClick={saveModule} disabled={submitting || !draftDirty}>
                  {mode === "create" ? t("modules.create") : t("modules.save")}
                </button>
              </div>
            </div>
            {panelError ? <div className="error-box">{panelError}</div> : null}
            {saved ? <div className="ok-box">{saved}</div> : null}
            <div className="form-grid">
              <div className="rule-field">
                <label htmlFor="module-name">{t("modules.fields.moduleName")}</label>
                <input
                  id="module-name"
                  value={draft.module_name}
                  onChange={(event) => setDraft((prev) => ({ ...prev, module_name: event.target.value }))}
                />
              </div>
              <div className="rule-field">
                <label htmlFor="module-id">{t("modules.fields.moduleId")}</label>
                <input
                  id="module-id"
                  value={activeModule?.module_id || t("modules.generatedAfterCreate")}
                  readOnly
                />
              </div>
              <div className="rule-field">
                <label htmlFor="module-host">{t("modules.fields.host")}</label>
                <input
                  id="module-host"
                  value={draft.host}
                  onChange={(event) => setDraft((prev) => ({ ...prev, host: event.target.value }))}
                />
              </div>
              <div className="rule-field">
                <label htmlFor="module-port">{t("modules.fields.port")}</label>
                <input
                  id="module-port"
                  type="number"
                  value={draft.port}
                  onChange={(event) => setDraft((prev) => ({ ...prev, port: event.target.value }))}
                />
              </div>
              <div className="rule-field">
                <label htmlFor="module-log-path">{t("modules.fields.accessLogPath")}</label>
                <input
                  id="module-log-path"
                  value={draft.access_log_path}
                  onChange={(event) => setDraft((prev) => ({ ...prev, access_log_path: event.target.value }))}
                />
              </div>
              <div className="rule-field">
                <label htmlFor="module-provider">{t("modules.fields.provider")}</label>
                <input
                  id="module-provider"
                  value={draft.provider}
                  onChange={(event) => setDraft((prev) => ({ ...prev, provider: event.target.value }))}
                />
              </div>
              <div className="rule-field rule-field-wide">
                <label htmlFor="module-config-profiles">{t("modules.fields.configProfiles")}</label>
                <textarea
                  id="module-config-profiles"
                  className="note-box"
                  value={draft.config_profiles}
                  onChange={(event) => setDraft((prev) => ({ ...prev, config_profiles: event.target.value }))}
                />
              </div>
              <div className="rule-field rule-field-wide">
                <label htmlFor="module-notes">{t("modules.fields.notes")}</label>
                <textarea
                  id="module-notes"
                  className="note-box"
                  value={draft.notes}
                  onChange={(event) => setDraft((prev) => ({ ...prev, notes: event.target.value }))}
                />
              </div>
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
                  onClick={() => copyText(detail?.install.compose_yaml || "", t("modules.composeCopied"))}
                >
                  {t("modules.copyCompose")}
                </button>
                <button
                  className="ghost"
                  disabled={loadingDetail || !activeModule?.token_reveal_available}
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

            {!activeModule?.token_reveal_available && mode === "detail" ? (
              <div className="provider-empty">{t("modules.tokenUnavailable")}</div>
            ) : null}

            {revealedToken ? (
              <div className="settings-group">
                <div className="panel-heading panel-heading-row">
                  <div>
                    <h3>{t("modules.tokenTitle")}</h3>
                    <p className="muted">{t("modules.tokenDescription")}</p>
                  </div>
                  <button className="ghost" onClick={() => copyText(revealedToken, t("modules.tokenCopied"))}>
                    {t("modules.copyToken")}
                  </button>
                </div>
                <div className="env-field-current">
                  <span className="muted">{t("modules.tokenValue")}</span>
                  <strong>{revealedToken}</strong>
                </div>
              </div>
            ) : null}

            <pre className="log-box module-compose-box">
              {detail?.install.compose_yaml || t("modules.installPreviewEmpty")}
            </pre>
          </div>
        </aside>
      </div>
    </section>
  );
}
