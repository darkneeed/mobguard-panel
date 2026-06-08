import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Loader2 } from "lucide-react";

import {
  api,
  AccessSettingsResponse,
  BrandingConfig,
  EnvFieldState,
  OwnerSecurityStatus,
} from "../api/client";
import { PaletteName, ThemeMode } from "../app/appearance";
import { BrandLogo } from "../components/BrandLogo";
import { FieldLabel } from "../components/FieldLabel";
import {
  buildEnvUpdates,
  buildInitialEnvDraft,
  isEnvDirty,
} from "../features/settings/lib/envFields";
import { Language, useI18n } from "../localization";
import { RULE_LIST_FIELDS } from "../rulesMeta";

const ACCESS_FIELDS = RULE_LIST_FIELDS.filter(
  (field) =>
    field.sectionKey === "access"
    && !["moderator_tg_ids", "viewer_tg_ids"].includes(field.key),
);

type AccessPageProps = {
  branding: BrandingConfig;
  onBrandingChange: (branding: BrandingConfig) => void;
  language: Language;
  onLanguageChange: (language: Language) => void;
  palette: PaletteName;
  onPaletteChange: (palette: PaletteName) => void;
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
};

function listValuesToText(values: Array<string | number> | undefined): string {
  return (values || []).map((item) => String(item)).join("\n");
}

export function AccessPage({
  branding,
  onBrandingChange,
  language,
  onLanguageChange,
  palette,
  onPaletteChange,
  theme,
  onThemeChange,
}: AccessPageProps) {
  const { t } = useI18n();
  const { section } = useParams<{ section?: string }>();
  const activeSection = section === "branding" ? "branding" : "access";
  const [data, setData] = useState<AccessSettingsResponse | null>(null);
  const [lists, setLists] = useState<Record<string, string>>({});
  const [savedLists, setSavedLists] = useState<Record<string, string>>({});
  const [brandingDraft, setBrandingDraft] = useState<BrandingConfig>(branding);
  const [savedBranding, setSavedBranding] = useState<BrandingConfig>(branding);
  const [remnawaveApiUrlDraft, setRemnawaveApiUrlDraft] = useState("");
  const [savedRemnawaveApiUrl, setSavedRemnawaveApiUrl] = useState("");
  const [bedolagaApiUrlDraft, setBedolagaApiUrlDraft] = useState("");
  const [savedBedolagaApiUrl, setSavedBedolagaApiUrl] = useState("");
  const [bedolagaApiTokenDraft, setBedolagaApiTokenDraft] = useState("");
  const [savedBedolagaApiToken, setSavedBedolagaApiToken] = useState("");
  const [bedolagaTimeoutDraft, setBedolagaTimeoutDraft] = useState(12);
  const [savedBedolagaTimeout, setSavedBedolagaTimeout] = useState(12);
  const [envDraft, setEnvDraft] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [brandingSaved, setBrandingSaved] = useState("");
  const [integrationSaved, setIntegrationSaved] = useState("");
  const [envError, setEnvError] = useState("");
  const [envSaved, setEnvSaved] = useState("");
  const [securityError, setSecurityError] = useState("");
  const [securitySaved, setSecuritySaved] = useState("");
  const [securitySubmitting, setSecuritySubmitting] = useState(false);
  const [listsSaving, setListsSaving] = useState(false);
  const [brandingSaving, setBrandingSaving] = useState(false);
  const [integrationSaving, setIntegrationSaving] = useState(false);
  const [envSaving, setEnvSaving] = useState(false);

  useEffect(() => {
    api
      .getAccessSettings()
      .then((payload) => {
        setData(payload);
        setLists(
          Object.fromEntries(
            ACCESS_FIELDS.map((field) => [
              field.key,
              listValuesToText(payload.lists[field.key]),
            ]),
          ),
        );
        setSavedLists(
          Object.fromEntries(
            ACCESS_FIELDS.map((field) => [
              field.key,
              listValuesToText(payload.lists[field.key]),
            ]),
          ),
        );
        setBrandingDraft(payload.settings);
        setSavedBranding(payload.settings);
        setRemnawaveApiUrlDraft(payload.settings.remnawave_api_url || "");
        setSavedRemnawaveApiUrl(payload.settings.remnawave_api_url || "");
        setBedolagaApiUrlDraft(payload.settings.bedolaga_api_url || "");
        setSavedBedolagaApiUrl(payload.settings.bedolaga_api_url || "");
        setBedolagaApiTokenDraft(payload.settings.bedolaga_api_token || "");
        setSavedBedolagaApiToken(payload.settings.bedolaga_api_token || "");
        setBedolagaTimeoutDraft(payload.settings.bedolaga_timeout_seconds ?? 12);
        setSavedBedolagaTimeout(payload.settings.bedolaga_timeout_seconds ?? 12);
        setEnvDraft(buildInitialEnvDraft(payload.env));
      })
      .catch((err: Error) => setError(err.message || t("access.loadFailed")));
  }, [t]);

  const brandingDirty = useMemo(
    () =>
      brandingDraft.panel_name !== savedBranding.panel_name
      || brandingDraft.panel_logo_url !== savedBranding.panel_logo_url,
    [brandingDraft, savedBranding],
  );
  const remnawaveDirty = useMemo(
    () => remnawaveApiUrlDraft !== savedRemnawaveApiUrl,
    [remnawaveApiUrlDraft, savedRemnawaveApiUrl],
  );
  const bedolagaDirty = useMemo(
    () =>
      bedolagaApiUrlDraft !== savedBedolagaApiUrl
      || bedolagaApiTokenDraft !== savedBedolagaApiToken
      || bedolagaTimeoutDraft !== savedBedolagaTimeout,
    [bedolagaApiUrlDraft, savedBedolagaApiUrl, bedolagaApiTokenDraft, savedBedolagaApiToken, bedolagaTimeoutDraft, savedBedolagaTimeout],
  );
  const integrationDirty = remnawaveDirty || bedolagaDirty;
  const listDirty = useMemo(
    () => JSON.stringify(lists) !== JSON.stringify(savedLists),
    [lists, savedLists],
  );
  const accessDirty = brandingDirty || integrationDirty || listDirty;
  const envDirty = useMemo(
    () => isEnvDirty(data?.env, envDraft),
    [data?.env, envDraft],
  );
  const envFieldCount = Object.values(data?.env || {}).length;
  const envPresentCount = Object.values(data?.env || {}).filter(
    (field) => field.present,
  ).length;

  function ownerSecurityStatus(
    security: OwnerSecurityStatus | undefined,
  ): string {
    if (!security) return t("common.notAvailable");
    return security.totp_enabled
      ? t("access.ownerSecurity.enabled")
      : t("access.ownerSecurity.disabled");
  }

  function parseNumberList(text: string): number[] {
    const values: number[] = [];
    for (const raw of text
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean)) {
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
      setListsSaving(true);
      const payload = {
        revision: data.revision,
        updated_at: data.updated_at,
        lists: Object.fromEntries(
          ACCESS_FIELDS.map((field) => [
            field.key,
            parseNumberList(lists[field.key] || ""),
          ]),
        ),
      };
      const response = await api.updateAccessSettings(payload);
      setData(response);
      const normalizedLists = Object.fromEntries(
        ACCESS_FIELDS.map((field) => [
          field.key,
          listValuesToText(response.lists[field.key]),
        ]),
      );
      setLists(normalizedLists);
      setSavedLists(normalizedLists);
      setEnvDraft(buildInitialEnvDraft(response.env));
      setSaved(t("access.saved"));
      setBrandingSaved("");
      setIntegrationSaved("");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("access.saveFailed"));
      setSaved("");
    } finally {
      setListsSaving(false);
    }
  }

  async function saveBranding() {
    if (!data) return;
    try {
      setBrandingSaving(true);
      const response = await api.updateAccessSettings({
        settings: {
          panel_name: brandingDraft.panel_name.trim(),
          panel_logo_url: brandingDraft.panel_logo_url.trim(),
        },
      });
      setData(response);
      setBrandingDraft(response.settings);
      setSavedBranding(response.settings);
      setRemnawaveApiUrlDraft(response.settings.remnawave_api_url || "");
      setSavedRemnawaveApiUrl(response.settings.remnawave_api_url || "");
      onBrandingChange(response.settings);
      setBrandingSaved(t("access.brandingSaved"));
      setIntegrationSaved("");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("access.saveFailed"));
      setBrandingSaved("");
    } finally {
      setBrandingSaving(false);
    }
  }

  async function saveIntegrations() {
    if (!data) return;
    try {
      setIntegrationSaving(true);
      const response = await api.updateAccessSettings({
        settings: {
          remnawave_api_url: remnawaveApiUrlDraft.trim(),
          bedolaga_api_url: bedolagaApiUrlDraft.trim(),
          bedolaga_api_token: bedolagaApiTokenDraft.trim(),
          bedolaga_timeout_seconds: Number(bedolagaTimeoutDraft),
        },
      });
      setData(response);
      setBrandingDraft(response.settings);
      setSavedBranding(response.settings);
      setRemnawaveApiUrlDraft(response.settings.remnawave_api_url || "");
      setSavedRemnawaveApiUrl(response.settings.remnawave_api_url || "");
      setBedolagaApiUrlDraft(response.settings.bedolaga_api_url || "");
      setSavedBedolagaApiUrl(response.settings.bedolaga_api_url || "");
      setBedolagaApiTokenDraft(response.settings.bedolaga_api_token || "");
      setSavedBedolagaApiToken(response.settings.bedolaga_api_token || "");
      setBedolagaTimeoutDraft(response.settings.bedolaga_timeout_seconds ?? 12);
      setSavedBedolagaTimeout(response.settings.bedolaga_timeout_seconds ?? 12);
      onBrandingChange(response.settings);
      setIntegrationSaved(t("access.integrationSaved"));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("access.saveFailed"));
      setIntegrationSaved("");
    } finally {
      setIntegrationSaving(false);
    }
  }

  async function saveEnv() {
    if (!data) return;
    const envUpdates = buildEnvUpdates(data.env, envDraft);
    if (Object.keys(envUpdates).length === 0) return;
    try {
      setEnvSaving(true);
      const response = await api.updateAccessSettings({
        env: envUpdates,
      });
      setData(response);
      setEnvDraft(buildInitialEnvDraft(response.env));
      setEnvSaved(t("access.envSaved"));
      setEnvError("");
    } catch (err) {
      setEnvError(err instanceof Error ? err.message : t("access.saveFailed"));
      setEnvSaved("");
    } finally {
      setEnvSaving(false);
    }
  }

  async function disableOwnerTotp() {
    if (!data) return;
    setSecuritySubmitting(true);
    try {
      const ownerSecurity = await api.disableOwnerTotp();
      setData((prev) => (prev ? { ...prev, owner_security: ownerSecurity } : prev));
      setSecuritySaved(t("access.ownerSecurity.disableSaved"));
      setSecurityError("");
    } catch (err) {
      setSecurityError(
        err instanceof Error ? err.message : t("access.saveFailed"),
      );
      setSecuritySaved("");
    } finally {
      setSecuritySubmitting(false);
    }
  }

  function renderEnvField(field: EnvFieldState) {
    return (
      <details
        className="settings-group settings-group-collapsible"
        key={field.key}
      >
        <summary className="settings-group-summary">
          <div>
            <h3>{field.key}</h3>
            <p className="muted">
              {field.masked
                ? t("common.secretValueStored")
                : t("common.runtimeValue")}
            </p>
          </div>
          <div className="action-row">
            <span
              className={
                field.present ? "tag status-resolved" : "tag severity-low"
              }
            >
              {field.present ? t("common.present") : t("common.missing")}
            </span>
            {field.restart_required ? (
              <span className="tag severity-high">
                {t("common.restartRequired")}
              </span>
            ) : null}
          </div>
        </summary>
        <div className="env-field-body">
          <div className="env-field-current">
            <span className="muted">{t("common.currentValue")}</span>
            <strong>{field.value || t("common.notAvailable")}</strong>
          </div>
          <input
            aria-label={field.key}
            placeholder={field.masked ? t("common.leaveBlankToKeep") : ""}
            value={envDraft[field.key] ?? ""}
            onChange={(event) =>
              setEnvDraft((prev) => ({
                ...prev,
                [field.key]: event.target.value,
              }))
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
          <h1>{t("nav.system")}</h1>
        </div>
        <div className="action-row">
          <span
            className={
              data?.env_file_writable
                ? "tag status-resolved"
                : "tag severity-high"
            }
          >
            {data?.env_file_writable
              ? t("common.writable")
              : t("common.readOnly")}
          </span>
          <span
            className={accessDirty ? "tag review-only" : "tag severity-low"}
          >
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
          {activeSection === "branding" ? (
            <div className="panel">
              <div className="panel-heading panel-heading-row">
                <div>
                  <h2>{t("access.brandingTitle")}</h2>
                  <p className="muted">{t("access.brandingDescription")}</p>
                </div>
                <div className="action-row">
                  <span
                    className={
                      brandingDirty ? "tag review-only" : "tag severity-low"
                    }
                  >
                    {brandingDirty
                      ? t("common.unsavedChanges")
                      : t("common.saved")}
                  </span>
                  <button
                    onClick={saveBranding}
                    disabled={!brandingDirty || !brandingDraft.panel_name.trim() || brandingSaving}
                  >
                    {brandingSaving && (
                      <Loader2 size={14} className="spinner" style={{ marginRight: "6px" }} />
                    )}
                    {t("access.saveBranding")}
                  </button>
                </div>
              </div>
              <div className="detail-grid">
                <div className="settings-group branding-preview-card">
                  <div className="brand">
                    <BrandLogo
                      logoUrl={brandingDraft.panel_logo_url}
                      alt={
                        brandingDraft.panel_name ||
                        t("access.brandingFields.serviceName")
                      }
                    />
                    <div className="branding-info">
                      <strong>
                        {brandingDraft.panel_name || t("common.notAvailable")}
                      </strong>
                      <small>{t("layout.brandSubtitle")}</small>
                    </div>
                  </div>
                </div>
                <div className="settings-group settings-group-stack">
                  <div className="rule-field">
                    <FieldLabel
                      label={t("access.brandingFields.serviceName")}
                      description={t(
                        "access.brandingFields.serviceNameDescription",
                      )}
                    />
                    <input
                      aria-label={t("access.brandingFields.serviceName")}
                      value={brandingDraft.panel_name}
                      onChange={(event) =>
                        setBrandingDraft((prev) => ({
                          ...prev,
                          panel_name: event.target.value,
                        }))
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
                        setBrandingDraft((prev) => ({
                          ...prev,
                          panel_logo_url: event.target.value,
                        }))
                      }
                    />
                  </div>
                </div>
                <div className="settings-group settings-group-stack">
                  <div>
                    <h3>{t("access.interfaceTitle")}</h3>
                    <p className="muted">{t("access.interfaceDescription")}</p>
                  </div>
                  <label className="theme-picker">
                    <span>{t("layout.language.label")}</span>
                    <select
                      value={language}
                      onChange={(event) =>
                        onLanguageChange(event.target.value as Language)
                      }
                    >
                      <option value="ru">{t("layout.language.ru")}</option>
                      <option value="en">{t("layout.language.en")}</option>
                    </select>
                  </label>
                  <label className="theme-picker">
                    <span>{t("layout.palette.label")}</span>
                    <select
                      value={palette}
                      onChange={(event) =>
                        onPaletteChange(event.target.value as PaletteName)
                      }
                    >
                      <option value="green">{t("layout.palette.green")}</option>
                      <option value="orange">{t("layout.palette.orange")}</option>
                      <option value="blue">{t("layout.palette.blue")}</option>
                      <option value="purple">{t("layout.palette.purple")}</option>
                      <option value="red">{t("layout.palette.red")}</option>
                    </select>
                  </label>
                  <label className="theme-picker">
                    <span>{t("layout.theme.label")}</span>
                    <select
                      value={theme}
                      onChange={(event) =>
                        onThemeChange(event.target.value as ThemeMode)
                      }
                    >
                      <option value="system">{t("layout.theme.system")}</option>
                      <option value="light">{t("layout.theme.light")}</option>
                      <option value="dark">{t("layout.theme.dark")}</option>
                    </select>
                  </label>
                  <p className="muted">{t("access.interfaceSavedHint")}</p>
                </div>
              </div>
            </div>
          ) : (
            <>
              <div className="stats-grid">
                <div className="stat-card">
                  <span>{t("access.cards.telegramLogin")}</span>
                  <strong>
                    {data.auth.telegram_enabled ? t("common.on") : t("common.off")}
                  </strong>
                </div>
                <div className="stat-card">
                  <span>{t("access.cards.localFallback")}</span>
                  <strong>
                    {data.auth.local_enabled ? t("common.on") : t("common.off")}
                  </strong>
                </div>
                <div className="stat-card">
                  <span>{t("access.cards.envFile")}</span>
                  <strong>
                    {data.env_file_writable
                      ? t("common.writable")
                      : t("common.readOnly")}
                  </strong>
                </div>
              </div>

              <div className="settings-grid">
                <div className="panel">
                  <div className="panel-heading panel-heading-row">
                    <div>
                      <h2>{t("access.integrationTitle")}</h2>
                      <p className="muted">{t("access.integrationDescription")}</p>
                    </div>
                    <div className="action-row">
                      <span
                        className={
                          integrationDirty ? "tag review-only" : "tag severity-low"
                        }
                      >
                        {integrationDirty
                          ? t("common.unsavedChanges")
                          : t("common.saved")}
                      </span>
                      <button onClick={saveIntegrations} disabled={!integrationDirty || integrationSaving}>
                        {integrationSaving && (
                          <Loader2 size={14} className="spinner" style={{ marginRight: "6px" }} />
                        )}
                        {t("access.saveIntegration")}
                      </button>
                    </div>
                  </div>
                  {integrationSaved ? <div className="ok-box">{integrationSaved}</div> : null}
                  <div className="settings-group settings-group-stack">
                    <div className="rule-field">
                      <FieldLabel
                        label={t("access.integrationFields.remnawaveApiUrl")}
                        description={t("access.integrationFields.remnawaveApiUrlDescription")}
                      />
                      <input
                        aria-label={t("access.integrationFields.remnawaveApiUrl")}
                        placeholder={t("access.integrationFields.remnawaveApiUrlPlaceholder")}
                        value={remnawaveApiUrlDraft}
                        onChange={(event) => setRemnawaveApiUrlDraft(event.target.value)}
                      />
                    </div>
                    <div className="rule-field">
                      <FieldLabel
                        label={t("access.integrationFields.bedolagaApiUrl")}
                        description={t("access.integrationFields.bedolagaApiUrlDescription")}
                      />
                      <input
                        aria-label={t("access.integrationFields.bedolagaApiUrl")}
                        placeholder="https://bedolaga.example.com"
                        value={bedolagaApiUrlDraft}
                        onChange={(event) => setBedolagaApiUrlDraft(event.target.value)}
                      />
                    </div>
                    <div className="rule-field">
                      <FieldLabel
                        label={t("access.integrationFields.bedolagaApiToken")}
                        description={t("access.integrationFields.bedolagaApiTokenDescription")}
                      />
                      <input
                        type="password"
                        aria-label={t("access.integrationFields.bedolagaApiToken")}
                        placeholder={t("common.leaveBlankToKeep")}
                        value={bedolagaApiTokenDraft}
                        onChange={(event) => setBedolagaApiTokenDraft(event.target.value)}
                      />
                    </div>
                    <div className="rule-field">
                      <FieldLabel
                        label={t("access.integrationFields.bedolagaTimeout")}
                        description={t("access.integrationFields.bedolagaTimeoutDescription")}
                      />
                      <input
                        type="number"
                        aria-label={t("access.integrationFields.bedolagaTimeout")}
                        value={bedolagaTimeoutDraft}
                        onChange={(event) => setBedolagaTimeoutDraft(Number(event.target.value))}
                      />
                    </div>
                  </div>
                </div>

                <div className="panel">
                  <div className="panel-heading panel-heading-row">
                    <div>
                      <h2>{t("access.listsTitle")}</h2>
                      <p className="muted">{t("access.listsDescription")}</p>
                    </div>
                    <div className="action-row">
                      <span
                        className={
                          listDirty ? "tag review-only" : "tag severity-low"
                        }
                      >
                        {listDirty ? t("common.unsavedChanges") : t("common.saved")}
                      </span>
                      <button onClick={save} disabled={!listDirty || listsSaving}>
                        {listsSaving && (
                          <Loader2 size={14} className="spinner" style={{ marginRight: "6px" }} />
                        )}
                        {t("access.save")}
                      </button>
                    </div>
                  </div>
                  <div className="detail-grid">
                    {ACCESS_FIELDS.map((field) => (
                      <div className="rule-field" key={field.key}>
                        <FieldLabel
                          label={t(`rulesMeta.listFields.${field.key}.label`)}
                          description={t(
                            `rulesMeta.listFields.${field.key}.description`,
                          )}
                          recommendation={t(
                            `rulesMeta.listFields.${field.key}.recommendation`,
                          )}
                        />
                        <textarea
                          className="note-box tall code-editor-box"
                          value={lists[field.key] || ""}
                          onChange={(event) =>
                            setLists((prev) => ({
                              ...prev,
                              [field.key]: event.target.value,
                            }))
                          }
                        />
                      </div>
                    ))}
                  </div>
                </div>

                <div className="panel">
                  <div className="panel-heading panel-heading-row">
                    <div>
                      <h2>{t("access.ownerSecurity.title")}</h2>
                      <p className="muted">{t("access.ownerSecurity.description")}</p>
                    </div>
                    <div className="action-row">
                      <span
                        className={
                          data.owner_security.totp_enabled
                            ? "tag review-only"
                            : "tag status-resolved"
                        }
                      >
                        {ownerSecurityStatus(data.owner_security)}
                      </span>
                      <button
                        onClick={disableOwnerTotp}
                        disabled={
                          securitySubmitting || !data.owner_security.enabled_owner_count
                        }
                      >
                        {securitySubmitting && (
                          <Loader2 size={14} className="spinner" style={{ marginRight: "6px" }} />
                        )}
                        {securitySubmitting
                          ? t("access.ownerSecurity.disabling")
                          : t("access.ownerSecurity.disableAction")}
                      </button>
                    </div>
                  </div>
                  {securityError ? <div className="error-box">{securityError}</div> : null}
                  {securitySaved ? <div className="ok-box">{securitySaved}</div> : null}
                  <div className="detail-list">
                    <div>
                      <dt>{t("access.ownerSecurity.statusLabel")}</dt>
                      <dd>{ownerSecurityStatus(data.owner_security)}</dd>
                    </div>
                    <div>
                      <dt>{t("access.ownerSecurity.ownerCountLabel")}</dt>
                      <dd>{data.owner_security.owner_identity_count}</dd>
                    </div>
                    <div>
                      <dt>{t("access.ownerSecurity.enabledCountLabel")}</dt>
                      <dd>{data.owner_security.enabled_owner_count}</dd>
                    </div>
                    <div>
                      <dt>{t("access.ownerSecurity.pendingLabel")}</dt>
                      <dd>{data.owner_security.pending_challenge_count}</dd>
                    </div>
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
                        {t("access.envCount", {
                          present: envPresentCount,
                          total: envFieldCount,
                        })}
                      </span>
                      <span
                        className={
                          envDirty ? "tag review-only" : "tag severity-low"
                        }
                      >
                        {envDirty ? t("common.unsavedChanges") : t("common.saved")}
                      </span>
                      <button
                        onClick={saveEnv}
                        disabled={!envDirty || !data.env_file_writable || envSaving}
                      >
                        {envSaving && (
                          <Loader2 size={14} className="spinner" style={{ marginRight: "6px" }} />
                        )}
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
          )}
        </>
      ) : null}
    </section>
  );
}
