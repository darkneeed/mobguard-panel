import { useEffect, useMemo, useState } from "react";

import {
  api,
  ModuleDetailResponse,
  ModuleListResponse,
  ModuleProvisioningPayload,
  ModuleRecord
} from "../api/client";
import { ModalShell } from "../components/ModalShell";
import { useToast } from "../components/ToastProvider";
import { useI18n } from "../localization";
import { formatDisplayDateTime } from "../utils/datetime";

type ModuleDraft = {
  module_name: string;
  inbound_tags: string;
};

const EMPTY_DRAFT: ModuleDraft = {
  module_name: "",
  inbound_tags: ""
};

function draftFromModule(module: ModuleRecord): ModuleDraft {
  return {
    module_name: module.module_name || "",
    inbound_tags: (module.inbound_tags || []).join("\n")
  };
}

function toProvisioningPayload(draft: ModuleDraft): ModuleProvisioningPayload {
  return {
    module_name: draft.module_name.trim(),
    inbound_tags: draft.inbound_tags
      .split(/\r?\n|,/)
      .map((item) => item.trim())
      .filter(Boolean)
  };
}

function statusVariant(module: ModuleRecord): string {
  if (module.install_state === "pending_install") {
    return "review-only";
  }
  if (!module.healthy) {
    return "severity-high";
  }
  if (module.health_status === "error") {
    return "punitive";
  }
  if (module.health_status === "warn") {
    return "severity-high";
  }
  return "status-resolved";
}

function statusLabelKey(module: ModuleRecord): string {
  if (module.install_state === "pending_install") {
    return "modules.pendingInstall";
  }
  if (!module.healthy) {
    return "modules.stale";
  }
  if (module.health_status === "error") {
    return "modules.health.error";
  }
  if (module.health_status === "warn") {
    return "modules.health.warn";
  }
  return "modules.health.ok";
}

export function ModulesPage() {
  const { t, language } = useI18n();
  const { pushToast } = useToast();
  const [data, setData] = useState<ModuleListResponse | null>(null);
  const [detail, setDetail] = useState<ModuleDetailResponse | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [modalMode, setModalMode] = useState<"create" | "detail" | null>(null);
  const [draft, setDraft] = useState<ModuleDraft>(EMPTY_DRAFT);
  const [savedDraft, setSavedDraft] = useState<ModuleDraft>(EMPTY_DRAFT);
  const [revealedToken, setRevealedToken] = useState("");
  const [error, setError] = useState("");
  const [panelError, setPanelError] = useState("");
  const [saved, setSaved] = useState("");
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const activeModule = modalMode === "detail" ? detail?.module ?? null : null;
  const draftDirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(savedDraft),
    [draft, savedDraft]
  );
  const modalOpen = modalMode !== null;
  const canSubmit =
    modalMode === "create"
      ? draftDirty && Boolean(draft.module_name.trim())
      : draftDirty;

  useEffect(() => {
    let cancelled = false;

    async function loadInitialState() {
      try {
        const listPayload = (await api.getModules()) as ModuleListResponse;
        if (cancelled) return;
        setData(listPayload);
        setError("");
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("modules.loadFailed"));
        }
      }
    }

    loadInitialState();
    return () => {
      cancelled = true;
    };
  }, [t]);

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
        const response = (await api.createModule(payload)) as ModuleDetailResponse;
        const nextDraft = draftFromModule(response.module);
        setModalMode("detail");
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
    const isActive = modalMode === "detail" && selectedId === item.module_id;

    return (
      <article
        className={`queue-card module-card ${isActive ? "module-card-active" : ""}`}
        key={item.module_id}
      >
        <div className="queue-card-top">
          <strong>{item.module_name}</strong>
          <span className={`status-badge ${statusVariant(item)}`}>{t(statusLabelKey(item))}</span>
        </div>
        <div className="queue-card-identifiers">
          <span>{t("modules.moduleId", { value: item.module_id })}</span>
          <span>{t("modules.version", { value: item.version || t("common.notAvailable") })}</span>
          <span>{t("modules.protocol", { value: item.protocol_version || "v1" })}</span>
        </div>
        <div className="queue-card-stack">
          <div className="queue-card-meta">
            <span>{t("modules.lastSeen")}</span>
            <strong>{formatDisplayDateTime(item.last_seen_at, t("common.notAvailable"), language)}</strong>
          </div>
          <div className="queue-card-meta">
            <span>{t("modules.inboundTags")}</span>
            <strong>{item.inbound_tags.length ? item.inbound_tags.join(", ") : t("common.notAvailable")}</strong>
          </div>
          <div className="queue-card-meta">
            <span>{t("modules.spoolDepth")}</span>
            <strong>{item.spool_depth}</strong>
          </div>
          <div className="queue-card-meta">
            <span>{t("modules.accessLogExists")}</span>
            <strong>{item.access_log_exists ? t("common.yes") : t("common.no")}</strong>
          </div>
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
          <span>{t("modules.cards.error")}</span>
          <strong>{data ? data.items.filter((item) => item.install_state !== "pending_install" && item.healthy && item.health_status === "error").length : "—"}</strong>
        </div>
        <div className="stat-card">
          <span>{t("modules.cards.stale")}</span>
          <strong>{data ? data.items.filter((item) => item.install_state !== "pending_install" && !item.healthy).length : "—"}</strong>
        </div>
      </div>

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
          {!data?.items.length ? <div className="provider-empty">{t("modules.empty")}</div> : null}
        </div>
      </div>

      <ModalShell
        open={modalOpen}
        onClose={closeModal}
        title={modalMode === "create" ? t("modules.createTitle") : t("modules.detailsTitle")}
        description={modalMode === "create" ? t("modules.createDescription") : t("modules.detailsDescription")}
        closeLabel={t("common.close")}
        actions={
          <div className="action-row">
            <span className={draftDirty ? "tag review-only" : "tag severity-low"}>
              {draftDirty ? t("common.unsavedChanges") : t("common.saved")}
            </span>
            <button onClick={saveModule} disabled={submitting || !canSubmit}>
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
                {modalMode === "create" ? t("modules.createDescription") : t("modules.detailsDescription")}
              </p>
            </div>
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
              <div className="rule-field rule-field-wide">
                <label htmlFor="module-inbound-tags">{t("modules.fields.inboundTags")}</label>
                <textarea
                  id="module-inbound-tags"
                  className="note-box"
                  value={draft.inbound_tags}
                  onChange={(event) => setDraft((prev) => ({ ...prev, inbound_tags: event.target.value }))}
                />
              </div>
            </div>
          </div>

          {modalMode === "detail" && loadingDetail && !detail ? (
            <div className="panel">{t("common.loading")}</div>
          ) : null}

          {modalMode === "detail" ? (
            <>
              <div className="panel">
                <div className="panel-heading">
                  <h2>{t("modules.healthTitle")}</h2>
                  <p className="muted">{t("modules.healthDescription")}</p>
                </div>
                {activeModule ? (
                  <div className="detail-list">
                    <div>
                      <dt>{t("modules.healthStatus")}</dt>
                      <dd>{t(statusLabelKey(activeModule))}</dd>
                    </div>
                    <div>
                      <dt>{t("modules.lastValidationAt")}</dt>
                      <dd>{formatDisplayDateTime(activeModule.last_validation_at, t("common.notAvailable"), language)}</dd>
                    </div>
                    <div>
                      <dt>{t("modules.spoolDepth")}</dt>
                      <dd>{activeModule.spool_depth}</dd>
                    </div>
                    <div>
                      <dt>{t("modules.accessLogExists")}</dt>
                      <dd>{activeModule.access_log_exists ? t("common.yes") : t("common.no")}</dd>
                    </div>
                  </div>
                ) : (
                  <div className="provider-empty">{t("modules.healthEmpty")}</div>
                )}
                {activeModule?.error_text ? <div className="error-box">{activeModule.error_text}</div> : null}
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

                {!activeModule?.token_reveal_available ? (
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

                <details className="export-section" open>
                  <summary>{t("modules.installTitle")}</summary>
                  <pre className="log-box module-compose-box">
                    {detail?.install.compose_yaml || t("modules.installPreviewEmpty")}
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
