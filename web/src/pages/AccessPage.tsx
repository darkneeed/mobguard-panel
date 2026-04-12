import { useEffect, useMemo, useState } from "react";

import { api, BrandingConfig, EnvFieldState } from "../api/client";
import { BrandLogo } from "../components/BrandLogo";
import { FieldLabel } from "../components/FieldLabel";
import {
  buildEnvUpdates,
  buildInitialEnvDraft,
  isEnvDirty
} from "../features/settings/lib/envFields";
import { useI18n } from "../localization";
import { RULE_LIST_FIELDS } from "../rulesMeta";

type AccessPayload = {
  revision: number;
  updated_at: string;
  updated_by: string;
  lists: Record<string, Array<string | number>>;
  settings: BrandingConfig;
  auth: {
    telegram_enabled: boolean;
    local_enabled: boolean;
    local_username_hint: string;
  };
  env: Record<string, EnvFieldState>;
  env_file_path: string;
  env_file_writable: boolean;
};

const ACCESS_FIELDS = RULE_LIST_FIELDS.filter((field) => field.sectionKey === "access");

type AccessPageProps = {
  branding: BrandingConfig;
  onBrandingChange: (branding: BrandingConfig) => void;
};

function listValuesToText(values: Array<string | number> | undefined): string {
  return (values || []).map((item) => String(item)).join("\n");
}

export function AccessPage({ branding, onBrandingChange }: AccessPageProps) {
  const { t } = useI18n();
  const [data, setData] = useState<AccessPayload | null>(null);
  const [lists, setLists] = useState<Record<string, string>>({});
  const [savedLists, setSavedLists] = useState<Record<string, string>>({});
  const [brandingDraft, setBrandingDraft] = useState<BrandingConfig>(branding);
  const [savedBranding, setSavedBranding] = useState<BrandingConfig>(branding);
  const [envDraft, setEnvDraft] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [brandingSaved, setBrandingSaved] = useState("");
  const [envError, setEnvError] = useState("");
  const [envSaved, setEnvSaved] = useState("");

  useEffect(() => {
    api
      .getAccessSettings()
      .then((payload) => {
        const typed = payload as AccessPayload;
        setData(typed);
        setLists(
          Object.fromEntries(
            ACCESS_FIELDS.map((field) => [field.key, listValuesToText(typed.lists[field.key])])
          )
        );
        setSavedLists(
          Object.fromEntries(
            ACCESS_FIELDS.map((field) => [field.key, listValuesToText(typed.lists[field.key])])
          )
        );
        setBrandingDraft(typed.settings);
        setSavedBranding(typed.settings);
        setEnvDraft(buildInitialEnvDraft(typed.env));
      })
      .catch((err: Error) => setError(err.message || t("access.loadFailed")));
  }, [t]);

  const brandingDirty = useMemo(
    () => JSON.stringify(brandingDraft) !== JSON.stringify(savedBranding),
    [brandingDraft, savedBranding]
  );
  const listDirty = useMemo(
    () => JSON.stringify(lists) !== JSON.stringify(savedLists),
    [lists, savedLists]
  );
  const accessDirty = brandingDirty || listDirty;
  const envDirty = useMemo(() => isEnvDirty(data?.env, envDraft), [data?.env, envDraft]);
  const envFieldCount = Object.values(data?.env || {}).length;
  const envPresentCount = Object.values(data?.env || {}).filter((field) => field.present).length;

  function parseNumberList(text: string): number[] {
    const values: number[] = [];
    for (const raw of text.split("\n").map((item) => item.trim()).filter(Boolean)) {
      const parsed = Number(raw);
      if (!Number.isFinite(parsed)) {
        throw new Error(t("access.invalidNumericValue", { value: raw }));
      }
      values.push(parsed);
    }
    return values;
  }

  async function save() {
    if (!data) return;
    try {
      const payload = {
        revision: data.revision,
        updated_at: data.updated_at,
        lists: Object.fromEntries(
          ACCESS_FIELDS.map((field) => [field.key, parseNumberList(lists[field.key] || "")])
        )
      };
      const response = (await api.updateAccessSettings(payload)) as AccessPayload;
      setData(response);
      const normalizedLists = Object.fromEntries(
        ACCESS_FIELDS.map((field) => [field.key, listValuesToText(response.lists[field.key])])
      );
      setLists(normalizedLists);
      setSavedLists(normalizedLists);
      setEnvDraft(buildInitialEnvDraft(response.env));
      setSaved(t("access.saved"));
      setBrandingSaved("");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("access.saveFailed"));
      setSaved("");
    }
  }

  async function saveBranding() {
    if (!data) return;
    try {
      const response = (await api.updateAccessSettings({
        settings: {
          panel_name: brandingDraft.panel_name.trim(),
          panel_logo_url: brandingDraft.panel_logo_url.trim(),
        }
      })) as AccessPayload;
      setData(response);
      setBrandingDraft(response.settings);
      setSavedBranding(response.settings);
      onBrandingChange(response.settings);
      setBrandingSaved(t("access.brandingSaved"));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("access.saveFailed"));
      setBrandingSaved("");
    }
  }

  async function saveEnv() {
    if (!data) return;
    const envUpdates = buildEnvUpdates(data.env, envDraft);
    if (Object.keys(envUpdates).length === 0) return;
    try {
      const response = (await api.updateAccessSettings({ env: envUpdates })) as AccessPayload;
      setData(response);
      setEnvDraft(buildInitialEnvDraft(response.env));
      setEnvSaved(t("access.envSaved"));
      setEnvError("");
    } catch (err) {
      setEnvError(err instanceof Error ? err.message : t("access.saveFailed"));
      setEnvSaved("");
    }
  }

  function renderEnvField(field: EnvFieldState) {
    return (
      <details className="settings-group settings-group-collapsible" key={field.key}>
        <summary className="settings-group-summary">
          <div>
            <h3>{field.key}</h3>
            <p className="muted">
              {field.masked ? t("common.secretValueStored") : t("common.runtimeValue")}
            </p>
          </div>
          <div className="action-row">
            <span className={field.present ? "tag status-resolved" : "tag severity-low"}>
              {field.present ? t("common.present") : t("common.missing")}
            </span>
            {field.restart_required ? (
              <span className="tag severity-high">{t("common.restartRequired")}</span>
            ) : null}
          </div>
        </summary>
        <div className="env-field-body">
        <div className="env-field-current">
          <span className="muted">{t("common.currentValue")}</span>
          <strong>{field.value || t("common.notAvailable")}</strong>
        </div>
        <input
          placeholder={field.masked ? t("common.leaveBlankToKeep") : ""}
          value={envDraft[field.key] ?? ""}
          onChange={(event) =>
            setEnvDraft((prev) => ({ ...prev, [field.key]: event.target.value }))
          }
        />
        </div>
      </details>
    );
  }

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <span className="eyebrow">{t("access.eyebrow")}</span>
          <h1>{t("access.title")}</h1>
        </div>
        <div className="action-row">
          <span className={data?.env_file_writable ? "tag status-resolved" : "tag severity-high"}>
            {data?.env_file_writable ? t("common.writable") : t("common.readOnly")}
          </span>
          <span className={accessDirty ? "tag review-only" : "tag severity-low"}>
            {accessDirty ? t("common.unsavedChanges") : t("common.saved")}
          </span>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {saved ? <div className="ok-box">{saved}</div> : null}
      {brandingSaved ? <div className="ok-box">{brandingSaved}</div> : null}
      {!data ? <div className="panel">{t("common.loading")}</div> : null}

      {data ? (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <span>{t("access.cards.telegramLogin")}</span>
              <strong>{data.auth.telegram_enabled ? t("common.on") : t("common.off")}</strong>
            </div>
            <div className="stat-card">
              <span>{t("access.cards.localFallback")}</span>
              <strong>{data.auth.local_enabled ? t("common.on") : t("common.off")}</strong>
            </div>
            <div className="stat-card">
              <span>{t("access.cards.envFile")}</span>
              <strong>{data.env_file_writable ? t("common.writable") : t("common.readOnly")}</strong>
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading panel-heading-row">
              <div>
                <h2>{t("access.brandingTitle")}</h2>
                <p className="muted">{t("access.brandingDescription")}</p>
              </div>
              <div className="action-row">
                <span className={brandingDirty ? "tag review-only" : "tag severity-low"}>
                  {brandingDirty ? t("common.unsavedChanges") : t("common.saved")}
                </span>
                <button onClick={saveBranding} disabled={!brandingDirty || !brandingDraft.panel_name.trim()}>
                  {t("access.saveBranding")}
                </button>
              </div>
            </div>
            <div className="detail-grid">
              <div className="settings-group branding-preview-card">
                <div className="brand">
                  <BrandLogo
                    logoUrl={brandingDraft.panel_logo_url}
                    alt={brandingDraft.panel_name || t("access.brandingFields.serviceName")}
                  />
                  <div>
                    <strong>{brandingDraft.panel_name || t("common.notAvailable")}</strong>
                    <small>{t("layout.brandSubtitle")}</small>
                  </div>
                </div>
              </div>
              <div className="rule-field">
                <FieldLabel
                  label={t("access.brandingFields.serviceName")}
                  description={t("access.brandingFields.serviceNameDescription")}
                />
                <input
                  aria-label={t("access.brandingFields.serviceName")}
                  value={brandingDraft.panel_name}
                  onChange={(event) =>
                    setBrandingDraft((prev) => ({ ...prev, panel_name: event.target.value }))
                  }
                />
              </div>
              <div className="rule-field">
                <FieldLabel
                  label={t("access.brandingFields.logoUrl")}
                  description={t("access.brandingFields.logoUrlDescription")}
                />
                <input
                  aria-label={t("access.brandingFields.logoUrl")}
                  placeholder={t("access.brandingFields.logoUrlPlaceholder")}
                  value={brandingDraft.panel_logo_url}
                  onChange={(event) =>
                    setBrandingDraft((prev) => ({ ...prev, panel_logo_url: event.target.value }))
                  }
                />
              </div>
            </div>
          </div>

          <div className="dashboard-grid">
            <div className="panel">
              <div className="panel-heading panel-heading-row">
                <div>
                  <h2>{t("access.listsTitle")}</h2>
                  <p className="muted">{t("access.listsDescription")}</p>
                </div>
                <div className="action-row">
                  <span className={listDirty ? "tag review-only" : "tag severity-low"}>
                    {listDirty ? t("common.unsavedChanges") : t("common.saved")}
                  </span>
                  <button onClick={save} disabled={!listDirty}>
                    {t("access.save")}
                  </button>
                </div>
              </div>
              <div className="detail-grid">
                {ACCESS_FIELDS.map((field) => (
                  <div className="rule-field" key={field.key}>
                    <FieldLabel
                      label={t(`rulesMeta.listFields.${field.key}.label`)}
                      description={t(`rulesMeta.listFields.${field.key}.description`)}
                      recommendation={t(`rulesMeta.listFields.${field.key}.recommendation`)}
                    />
                    <textarea
                      className="note-box tall"
                      value={lists[field.key] || ""}
                      onChange={(event) =>
                        setLists((prev) => ({ ...prev, [field.key]: event.target.value }))
                      }
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="panel">
              <div className="panel-heading panel-heading-row">
                <div>
                  <h2>{t("access.envTitle")}</h2>
                  <p className="muted">{t("access.envDescription")}</p>
                </div>
                <div className="action-row">
                  <span className="tag severity-low">
                    {t("access.envCount", { present: envPresentCount, total: envFieldCount })}
                  </span>
                  <span className={envDirty ? "tag review-only" : "tag severity-low"}>
                    {envDirty ? t("common.unsavedChanges") : t("common.saved")}
                  </span>
                  <button onClick={saveEnv} disabled={!envDirty || !data.env_file_writable}>
                    {t("access.saveEnv")}
                  </button>
                </div>
              </div>
              <div className="settings-group-stack">
                <div className="settings-file-row">
                  <span className="muted">{t("common.envFile")}</span>
                  <strong>{data.env_file_path}</strong>
                </div>
                {envError ? <div className="error-box">{envError}</div> : null}
                {envSaved ? <div className="ok-box">{envSaved}</div> : null}
                {Object.values(data.env).map(renderEnvField)}
              </div>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
