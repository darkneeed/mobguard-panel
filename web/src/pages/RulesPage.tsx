import { useEffect, useState } from "react";

import { api, RulesState } from "../api/client";
import { FieldLabel } from "../components/FieldLabel";
import {
  getSettingInputValue,
  listValuesToText,
  normalizeGeneralSettingsDraft,
  normalizeRulesDraft,
  parseListText
} from "../features/rules/lib/serializers";
import { useI18n } from "../localization";
import {
  RULE_LIST_FIELDS,
  RULE_SETTING_FIELDS,
  RuleListFieldMeta,
  RuleSettingFieldMeta,
  RuleSettingValue,
  RulesDraft
} from "../rulesMeta";
import { formatDisplayDateTime } from "../utils/datetime";

type EnforcementPayload = {
  settings: Record<string, string | number | boolean | string[]>;
};

type GeneralSettingKey =
  | "usage_time_threshold"
  | "warning_timeout_seconds"
  | "warnings_before_ban"
  | "warning_only_mode"
  | "manual_review_mixed_home_enabled"
  | "manual_ban_approval_enabled"
  | "dry_run"
  | "ban_durations_minutes";

type GeneralSettingField = {
  key: GeneralSettingKey;
  inputType: "number" | "boolean" | "number-list";
  step?: number;
};

const GENERAL_SETTINGS_FIELDS: GeneralSettingField[] = [
  { key: "usage_time_threshold", inputType: "number" },
  { key: "warning_timeout_seconds", inputType: "number" },
  { key: "warnings_before_ban", inputType: "number" },
  { key: "warning_only_mode", inputType: "boolean" },
  { key: "manual_review_mixed_home_enabled", inputType: "boolean" },
  { key: "manual_ban_approval_enabled", inputType: "boolean" },
  { key: "dry_run", inputType: "boolean" },
  { key: "ban_durations_minutes", inputType: "number-list" }
];

const LIST_SECTIONS = Array.from(
  new Set(RULE_LIST_FIELDS.filter((field) => field.sectionKey !== "access").map((field) => field.sectionKey))
);
const SETTING_SECTIONS = Array.from(new Set(RULE_SETTING_FIELDS.map((field) => field.sectionKey)));

export function RulesPage() {
  const { t, language } = useI18n();
  const [state, setState] = useState<RulesState | null>(null);
  const [draft, setDraft] = useState<RulesDraft | null>(null);
  const [savedDraft, setSavedDraft] = useState<RulesDraft | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const [generalDraft, setGeneralDraft] = useState<Record<string, string> | null>(null);
  const [savedGeneralDraft, setSavedGeneralDraft] = useState<Record<string, string> | null>(null);
  const [generalError, setGeneralError] = useState("");
  const [generalSaved, setGeneralSaved] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [detectionPayload, enforcementPayload] = await Promise.all([
          api.getDetectionSettings(),
          api.getEnforcementSettings()
        ]);
        if (cancelled) return;

        const typedDetection = detectionPayload as RulesState;
        const normalizedRules = normalizeRulesDraft(typedDetection.rules);
        const typedEnforcement = enforcementPayload as EnforcementPayload;
        const normalizedGeneral = normalizeGeneralSettingsDraft(typedEnforcement.settings, GENERAL_SETTINGS_FIELDS);

        setState(typedDetection);
        setDraft(normalizedRules);
        setSavedDraft(normalizedRules);
        setGeneralDraft(normalizedGeneral);
        setSavedGeneralDraft(normalizedGeneral);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("rules.loadFailed"));
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [t]);

  const dirty = JSON.stringify(draft) !== JSON.stringify(savedDraft);
  const generalDirty = JSON.stringify(generalDraft) !== JSON.stringify(savedGeneralDraft);

  function listFieldMeta(field: RuleListFieldMeta) {
    return {
      label: t(`rulesMeta.listFields.${field.key}.label`),
      description: t(`rulesMeta.listFields.${field.key}.description`),
      recommendation: t(`rulesMeta.listFields.${field.key}.recommendation`)
    };
  }

  function settingFieldMeta(field: RuleSettingFieldMeta) {
    return {
      label: t(`rulesMeta.settingFields.${field.key}.label`),
      description: t(`rulesMeta.settingFields.${field.key}.description`),
      recommendation: t(`rulesMeta.settingFields.${field.key}.recommendation`)
    };
  }

  function generalFieldMeta(key: GeneralSettingKey) {
    return {
      label: t(`rulesMeta.rulesGeneralFields.${key}.label`),
      description: t(`rulesMeta.rulesGeneralFields.${key}.description`)
    };
  }

  function serializeListField(meta: RuleListFieldMeta, values: Array<string | number> | undefined) {
    const rawValues = (values || []).map((item) => String(item).trim()).filter(Boolean);
    if (meta.itemType === "string") {
      return rawValues;
    }

    const serialized: number[] = [];
    const label = listFieldMeta(meta).label;
    for (const item of rawValues) {
      const parsed = Number(item);
      if (!Number.isFinite(parsed)) {
        throw new Error(t("rules.invalidValue", { field: label, value: item }));
      }
      serialized.push(parsed);
    }
    return serialized;
  }

  function serializeSettingField(meta: RuleSettingFieldMeta, value: RuleSettingValue) {
    if (meta.inputType === "boolean") {
      return Boolean(value);
    }
    if (meta.inputType === "text") {
      return String(value ?? "").trim();
    }

    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      throw new Error(t("rules.invalidNumber", { field: settingFieldMeta(meta).label }));
    }
    return parsed;
  }

  function serializeGeneralSettings(draftValues: Record<string, string>) {
    const payload: Record<string, unknown> = {};

    for (const field of GENERAL_SETTINGS_FIELDS) {
      const rawValue = draftValues[field.key] ?? "";
      const label = generalFieldMeta(field.key).label;
      if (field.inputType === "boolean") {
        payload[field.key] = rawValue === "true";
        continue;
      }
      if (field.inputType === "number-list") {
        payload[field.key] = rawValue
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean)
          .map((item) => {
            const parsed = Number(item);
            if (!Number.isFinite(parsed)) {
              throw new Error(t("rules.invalidValue", { field: label, value: item }));
            }
            return parsed;
          });
        continue;
      }

      const parsed = Number(rawValue);
      if (!Number.isFinite(parsed)) {
        throw new Error(t("rules.invalidNumber", { field: label }));
      }
      payload[field.key] = parsed;
    }

    return payload;
  }

  async function save() {
    if (!draft || !state) return;
    try {
      const payload: Record<string, unknown> = { settings: {} };

      for (const field of RULE_LIST_FIELDS) {
        payload[field.key] = serializeListField(field, draft[field.key]);
      }

      for (const field of RULE_SETTING_FIELDS) {
        payload.settings = {
          ...(payload.settings as Record<string, unknown>),
          [field.key]: serializeSettingField(field, draft.settings?.[field.key])
        };
      }

      const updated = (await api.updateDetectionSettings({
        rules: payload,
        revision: state.revision,
        updated_at: state.updated_at
      })) as RulesState;
      const normalized = normalizeRulesDraft(updated.rules);
      setState(updated);
      setDraft(normalized);
      setSavedDraft(normalized);
      setError("");
      setSaved(t("rules.rulesUpdated"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("rules.saveFailed"));
      setSaved("");
    }
  }

  async function saveGeneralSettings() {
    if (!generalDraft) return;
    try {
      const response = (await api.updateEnforcementSettings({
        settings: serializeGeneralSettings(generalDraft)
      })) as EnforcementPayload;
      const normalized = normalizeGeneralSettingsDraft(response.settings, GENERAL_SETTINGS_FIELDS);
      setGeneralDraft(normalized);
      setSavedGeneralDraft(normalized);
      setGeneralError("");
      setGeneralSaved(t("rules.generalSaved"));
    } catch (err) {
      setGeneralError(err instanceof Error ? err.message : t("rules.saveFailed"));
      setGeneralSaved("");
    }
  }

  function updateListField(meta: RuleListFieldMeta, text: string) {
    setDraft((prev) => ({
      ...(prev || {}),
      [meta.key]: parseListText(text),
      settings: prev?.settings || {}
    }));
    setSaved("");
  }

  function updateSettingField(meta: RuleSettingFieldMeta, value: string) {
    setDraft((prev) => ({
      ...(prev || {}),
      settings: {
        ...(prev?.settings || {}),
        [meta.key]: meta.inputType === "boolean" ? value === "true" : value
      }
    }));
    setSaved("");
  }

  function updateGeneralField(key: string, value: string) {
    setGeneralDraft((prev) => ({
      ...(prev || {}),
      [key]: value
    }));
    setGeneralSaved("");
  }

  const updatedBy = !state?.updated_by || state.updated_by === "bootstrap" ? t("common.system") : state.updated_by;

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">{t("rules.eyebrow")}</span>
          <h1>{t("rules.title")}</h1>
        </div>
        <div className="action-row">
          <span className={dirty ? "tag review-only" : "tag severity-low"}>
            {dirty ? t("common.unsavedChanges") : t("common.saved")}
          </span>
          <button disabled={!dirty} onClick={save}>
            {t("rules.saveRules")}
          </button>
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      {saved ? <div className="ok-box">{saved}</div> : null}
      {state ? (
        <div className="panel queue-footer">
          <span>{t("rules.revision", { value: state.revision })}</span>
          <span>{t("rules.updatedAt", { value: formatDisplayDateTime(state.updated_at, t("common.notAvailable"), language) })}</span>
          <span>{t("rules.updatedBy", { value: updatedBy })}</span>
        </div>
      ) : null}
      {!draft && !generalDraft ? <div className="panel">{t("common.loading")}</div> : null}

      {generalDraft ? (
        <div className="panel">
          <div className="panel-heading panel-heading-row">
            <div>
              <h2>{t("rules.general.title")}</h2>
              <p className="muted">{t("rules.general.description")}</p>
            </div>
            <div className="action-row">
              <span className={generalDirty ? "tag review-only" : "tag severity-low"}>
                {generalDirty ? t("common.unsavedChanges") : t("common.saved")}
              </span>
              <button disabled={!generalDirty} onClick={saveGeneralSettings}>
                {t("rules.general.save")}
              </button>
            </div>
          </div>
          {generalError ? <div className="error-box">{generalError}</div> : null}
          {generalSaved ? <div className="ok-box">{generalSaved}</div> : null}
          <div className="form-grid">
            {GENERAL_SETTINGS_FIELDS.map((field) => {
              const meta = generalFieldMeta(field.key);
              return (
                <div
                  className={field.inputType === "number-list" ? "rule-field rule-field-wide" : "rule-field"}
                  key={field.key}
                >
                  <FieldLabel label={meta.label} description={meta.description} />
                  {field.inputType === "boolean" ? (
                    <select
                      value={generalDraft[field.key] || "false"}
                      onChange={(event) => updateGeneralField(field.key, event.target.value)}
                    >
                      <option value="true">{t("common.true")}</option>
                      <option value="false">{t("common.false")}</option>
                    </select>
                  ) : field.inputType === "number-list" ? (
                    <textarea
                      className="note-box tall"
                      value={generalDraft[field.key] || ""}
                      onChange={(event) => updateGeneralField(field.key, event.target.value)}
                    />
                  ) : (
                    <input
                      type="number"
                      step={field.step}
                      value={generalDraft[field.key] || ""}
                      onChange={(event) => updateGeneralField(field.key, event.target.value)}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {draft ? (
        <div className="page">
          {LIST_SECTIONS.map((section) => (
            <div className="panel" key={section}>
              <div className="panel-heading">
                <h2>{t(`rulesMeta.sections.${section}`)}</h2>
                <p className="muted">{t("rules.listSectionDescription")}</p>
              </div>
              <div className="detail-grid">
                {RULE_LIST_FIELDS.filter((field) => field.sectionKey === section).map((field) => {
                  const meta = listFieldMeta(field);
                  return (
                    <div className="rule-field" key={field.key}>
                      <FieldLabel
                        label={meta.label}
                        description={meta.description}
                        recommendation={meta.recommendation}
                      />
                      <textarea
                        className="note-box tall"
                        value={listValuesToText(draft[field.key])}
                        onChange={(event) => updateListField(field, event.target.value)}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          {SETTING_SECTIONS.map((section) => (
            <div className="panel" key={section}>
              <div className="panel-heading">
                <h2>{t(`rulesMeta.sections.${section}`)}</h2>
                <p className="muted">{t("rules.settingSectionDescription")}</p>
              </div>
              <div className="form-grid">
                {RULE_SETTING_FIELDS.filter((field) => field.sectionKey === section).map((field) => {
                  const meta = settingFieldMeta(field);
                  return (
                    <div className="rule-field" key={field.key}>
                      <FieldLabel
                        label={meta.label}
                        description={meta.description}
                        recommendation={meta.recommendation}
                      />
                      {field.inputType === "boolean" ? (
                        <select
                          value={getSettingInputValue(field, draft.settings?.[field.key])}
                          onChange={(event) => updateSettingField(field, event.target.value)}
                        >
                          <option value="true">{t("common.true")}</option>
                          <option value="false">{t("common.false")}</option>
                        </select>
                      ) : (
                        <input
                          type={field.inputType === "number" ? "number" : "text"}
                          step={field.step}
                          value={getSettingInputValue(field, draft.settings?.[field.key])}
                          onChange={(event) => updateSettingField(field, event.target.value)}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
