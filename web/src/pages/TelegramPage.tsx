import { useEffect, useMemo, useState } from "react";

import { api, EnvFieldState } from "../api/client";
import { FieldLabel } from "../components/FieldLabel";
import { InfoTooltip } from "../components/InfoTooltip";
import {
  buildEnvUpdates,
  buildInitialEnvDraft,
  isEnvDirty
} from "../features/settings/lib/envFields";
import { useI18n } from "../localization";

type TelegramPayload = {
  settings: Record<string, string | number | boolean>;
  env: Record<string, EnvFieldState>;
  capabilities: {
    admin_bot_enabled: boolean;
    user_bot_enabled: boolean;
  };
  env_file_path: string;
  env_file_writable: boolean;
};

type EnforcementPayload = {
  settings: Record<string, string | number | boolean | string[]>;
};

type TelegramFieldKey =
  | "tg_admin_chat_id"
  | "tg_topic_id"
  | "telegram_message_min_interval_seconds"
  | "telegram_admin_notifications_enabled"
  | "telegram_user_notifications_enabled"
  | "telegram_admin_commands_enabled"
  | "telegram_notify_admin_review_enabled"
  | "telegram_notify_admin_warning_only_enabled"
  | "telegram_notify_admin_warning_enabled"
  | "telegram_notify_admin_ban_enabled"
  | "telegram_notify_user_warning_only_enabled"
  | "telegram_notify_user_warning_enabled"
  | "telegram_notify_user_ban_enabled";

type TemplateFieldKey =
  | "user_warning_only_template"
  | "user_warning_template"
  | "user_ban_template"
  | "admin_warning_only_template"
  | "admin_warning_template"
  | "admin_ban_template"
  | "admin_review_template";

type TelegramField = {
  key: TelegramFieldKey;
  section: "delivery" | "admin" | "user";
  type: "text" | "number" | "boolean";
  step?: number;
};

type TemplateField = {
  key: TemplateFieldKey;
  audience: "admin" | "user";
};

const TELEGRAM_FIELDS: TelegramField[] = [
  { key: "tg_admin_chat_id", section: "delivery", type: "text" },
  { key: "tg_topic_id", section: "delivery", type: "number" },
  { key: "telegram_message_min_interval_seconds", section: "delivery", type: "number", step: 0.1 },
  { key: "telegram_admin_notifications_enabled", section: "delivery", type: "boolean" },
  { key: "telegram_user_notifications_enabled", section: "delivery", type: "boolean" },
  { key: "telegram_admin_commands_enabled", section: "delivery", type: "boolean" },
  { key: "telegram_notify_admin_review_enabled", section: "admin", type: "boolean" },
  { key: "telegram_notify_admin_warning_only_enabled", section: "admin", type: "boolean" },
  { key: "telegram_notify_admin_warning_enabled", section: "admin", type: "boolean" },
  { key: "telegram_notify_admin_ban_enabled", section: "admin", type: "boolean" },
  { key: "telegram_notify_user_warning_only_enabled", section: "user", type: "boolean" },
  { key: "telegram_notify_user_warning_enabled", section: "user", type: "boolean" },
  { key: "telegram_notify_user_ban_enabled", section: "user", type: "boolean" }
];

const TEMPLATE_FIELDS: TemplateField[] = [
  { key: "user_warning_only_template", audience: "user" },
  { key: "user_warning_template", audience: "user" },
  { key: "user_ban_template", audience: "user" },
  { key: "admin_warning_only_template", audience: "admin" },
  { key: "admin_warning_template", audience: "admin" },
  { key: "admin_ban_template", audience: "admin" },
  { key: "admin_review_template", audience: "admin" }
];

function normalizeTelegramDraft(payload: TelegramPayload): Record<string, string> {
  return Object.fromEntries(
    TELEGRAM_FIELDS.map((field) => [field.key, String(payload.settings[field.key] ?? "")])
  );
}

function normalizeTemplateDraft(payload: EnforcementPayload): Record<string, string> {
  return Object.fromEntries(
    TEMPLATE_FIELDS.map((field) => [field.key, String(payload.settings[field.key] ?? "")])
  );
}

export function TelegramPage() {
  const { t } = useI18n();
  const [data, setData] = useState<TelegramPayload | null>(null);
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [savedSettings, setSavedSettings] = useState<Record<string, string>>({});
  const [envDraft, setEnvDraft] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [envError, setEnvError] = useState("");
  const [envSaved, setEnvSaved] = useState("");

  const [templates, setTemplates] = useState<Record<string, string>>({});
  const [savedTemplates, setSavedTemplates] = useState<Record<string, string>>({});
  const [templatesError, setTemplatesError] = useState("");
  const [templatesSaved, setTemplatesSaved] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [telegramPayload, enforcementPayload] = await Promise.all([
          api.getTelegramSettings(),
          api.getEnforcementSettings()
        ]);
        if (cancelled) return;

        const typedTelegram = telegramPayload as TelegramPayload;
        const normalizedTelegram = normalizeTelegramDraft(typedTelegram);
        const typedEnforcement = enforcementPayload as EnforcementPayload;
        const normalizedTemplates = normalizeTemplateDraft(typedEnforcement);

        setData(typedTelegram);
        setSettings(normalizedTelegram);
        setSavedSettings(normalizedTelegram);
        setEnvDraft(buildInitialEnvDraft(typedTelegram.env));
        setTemplates(normalizedTemplates);
        setSavedTemplates(normalizedTemplates);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("telegram.loadFailed"));
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [t]);

  const runtimeDirty = JSON.stringify(settings) !== JSON.stringify(savedSettings);
  const envDirty = useMemo(() => isEnvDirty(data?.env, envDraft), [data?.env, envDraft]);
  const templatesDirty = JSON.stringify(templates) !== JSON.stringify(savedTemplates);
  const envFieldCount = Object.values(data?.env || {}).length;
  const envPresentCount = Object.values(data?.env || {}).filter((field) => field.present).length;

  function fieldMeta(key: TelegramFieldKey) {
    return {
      label: t(`rulesMeta.telegramFields.${key}.label`),
      description: t(`rulesMeta.telegramFields.${key}.description`)
    };
  }

  function templateMeta(key: TemplateFieldKey) {
    return {
      label: t(`rulesMeta.telegramTemplateFields.${key}.label`),
      description: t(`rulesMeta.telegramTemplateFields.${key}.description`)
    };
  }

  async function saveRuntime() {
    if (!data) return;
    try {
      const settingsPayload = Object.fromEntries(
        TELEGRAM_FIELDS.map((field) => {
          if (field.type === "boolean") {
            return [field.key, settings[field.key] === "true"];
          }
          if (field.type === "number") {
            const parsed = Number(settings[field.key]);
            if (!Number.isFinite(parsed)) {
              throw new Error(t("telegram.invalidNumber", { field: fieldMeta(field.key).label }));
            }
            return [field.key, parsed];
          }
          return [field.key, settings[field.key]];
        })
      );
      const response = (await api.updateTelegramSettings({
        settings: settingsPayload
      })) as TelegramPayload;
      const normalized = normalizeTelegramDraft(response);
      setData(response);
      setSettings(normalized);
      setSavedSettings(normalized);
      setEnvDraft(buildInitialEnvDraft(response.env));
      setSaved(t("telegram.settingsSaved"));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("telegram.saveFailed"));
      setSaved("");
    }
  }

  async function saveEnv() {
    if (!data) return;
    const envUpdates = buildEnvUpdates(data.env, envDraft);
    if (Object.keys(envUpdates).length === 0) return;
    try {
      const response = (await api.updateTelegramSettings({
        env: envUpdates
      })) as TelegramPayload;
      const normalized = normalizeTelegramDraft(response);
      setData(response);
      setSettings(normalized);
      setSavedSettings(normalized);
      setEnvDraft(buildInitialEnvDraft(response.env));
      setEnvSaved(t("telegram.envSaved"));
      setEnvError("");
    } catch (err) {
      setEnvError(err instanceof Error ? err.message : t("telegram.saveFailed"));
      setEnvSaved("");
    }
  }

  async function saveTemplates() {
    try {
      const response = (await api.updateEnforcementSettings({
        settings: Object.fromEntries(
          TEMPLATE_FIELDS.map((field) => [field.key, templates[field.key] ?? ""])
        )
      })) as EnforcementPayload;
      const normalized = normalizeTemplateDraft(response);
      setTemplates(normalized);
      setSavedTemplates(normalized);
      setTemplatesSaved(t("telegram.templatesSaved"));
      setTemplatesError("");
    } catch (err) {
      setTemplatesError(err instanceof Error ? err.message : t("telegram.saveFailed"));
      setTemplatesSaved("");
    }
  }

  function renderTelegramField(field: TelegramField) {
    const meta = fieldMeta(field.key);
    return (
      <div className="rule-field" key={field.key}>
        <FieldLabel label={meta.label} description={meta.description} />
        {field.type === "boolean" ? (
          <select
            value={settings[field.key]}
            onChange={(event) =>
              setSettings((prev) => ({ ...prev, [field.key]: event.target.value }))
            }
          >
            <option value="true">{t("common.true")}</option>
            <option value="false">{t("common.false")}</option>
          </select>
        ) : (
          <input
            type={field.type === "number" ? "number" : "text"}
            step={field.step}
            value={settings[field.key]}
            onChange={(event) =>
              setSettings((prev) => ({ ...prev, [field.key]: event.target.value }))
            }
          />
        )}
      </div>
    );
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
          <span className="eyebrow">{t("telegram.eyebrow")}</span>
          <h1>{t("telegram.title")}</h1>
        </div>
        <div className="action-row">
          <span className={runtimeDirty ? "tag review-only" : "tag severity-low"}>
            {runtimeDirty ? t("common.unsavedChanges") : t("common.saved")}
          </span>
          <button onClick={saveRuntime} disabled={!data || !runtimeDirty}>
            {t("telegram.saveSettings")}
          </button>
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      {saved ? <div className="ok-box">{saved}</div> : null}
      {!data ? <div className="panel">{t("common.loading")}</div> : null}

      {data ? (
        <>
            <div className="stats-grid">
              <div className="stat-card">
                <span>{t("telegram.cards.adminBot")}</span>
                <strong>{data.capabilities.admin_bot_enabled ? t("common.on") : t("common.off")}</strong>
              </div>
              <div className="stat-card">
                <span>{t("telegram.cards.userBot")}</span>
                <strong>{data.capabilities.user_bot_enabled ? t("common.on") : t("common.off")}</strong>
              </div>
              <div className="stat-card">
                <span>{t("telegram.cards.envFile")}</span>
                <strong>{data.env_file_writable ? t("common.writable") : t("common.readOnly")}</strong>
              </div>
            </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>{t("telegram.deliveryTitle")}</h2>
              <p className="muted">{t("telegram.deliveryDescription")}</p>
            </div>
            <div className="form-grid">
              {TELEGRAM_FIELDS.filter((field) => field.section === "delivery").map(renderTelegramField)}
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>{t("telegram.adminNotificationsTitle")}</h2>
              <p className="muted">{t("telegram.adminNotificationsDescription")}</p>
            </div>
            <div className="form-grid">
              {TELEGRAM_FIELDS.filter((field) => field.section === "admin").map(renderTelegramField)}
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <h2>{t("telegram.userNotificationsTitle")}</h2>
              <p className="muted">{t("telegram.userNotificationsDescription")}</p>
            </div>
            <div className="form-grid">
              {TELEGRAM_FIELDS.filter((field) => field.section === "user").map(renderTelegramField)}
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading panel-heading-row">
              <div>
                <h2>{t("telegram.envTitle")}</h2>
                <p className="muted">{t("telegram.envDescription")}</p>
              </div>
              <div className="action-row">
                <span className="tag severity-low">
                  {t("telegram.envCount", { present: envPresentCount, total: envFieldCount })}
                </span>
                <span className={envDirty ? "tag review-only" : "tag severity-low"}>
                  {envDirty ? t("common.unsavedChanges") : t("common.saved")}
                </span>
                <button disabled={!envDirty || !data.env_file_writable} onClick={saveEnv}>
                  {t("telegram.saveEnv")}
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

          <div className="panel">
            <div className="panel-heading panel-heading-row">
              <div className="action-row">
                <h2>{t("telegram.templatesTitle")}</h2>
                <InfoTooltip
                  label={t("telegram.templatesHintLabel")}
                  content={t("telegram.templatesHint")}
                />
              </div>
              <div className="action-row">
                <span className={templatesDirty ? "tag review-only" : "tag severity-low"}>
                  {templatesDirty ? t("common.unsavedChanges") : t("common.saved")}
                </span>
                <button disabled={!templatesDirty} onClick={saveTemplates}>
                  {t("telegram.saveTemplates")}
                </button>
              </div>
            </div>
            {templatesError ? <div className="error-box">{templatesError}</div> : null}
            {templatesSaved ? <div className="ok-box">{templatesSaved}</div> : null}
            <div className="detail-grid">
              {(["user", "admin"] as const).map((audience) => (
                <div className="settings-group" key={audience}>
                  <h3>{audience === "user" ? t("telegram.userTemplates") : t("telegram.adminTemplates")}</h3>
                  <div className="settings-group-fields">
                    {TEMPLATE_FIELDS.filter((field) => field.audience === audience).map((field) => {
                      const meta = templateMeta(field.key);
                      return (
                        <div className="rule-field" key={field.key}>
                          <FieldLabel label={meta.label} description={meta.description} />
                          <textarea
                            className="note-box tall"
                            value={templates[field.key] || ""}
                            onChange={(event) =>
                              setTemplates((prev) => ({ ...prev, [field.key]: event.target.value }))
                            }
                          />
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
