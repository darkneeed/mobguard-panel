import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

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
  ProviderProfileDraft,
  RULE_LIST_FIELDS,
  RULE_SETTING_FIELDS,
  RuleListFieldMeta,
  RuleSettingFieldMeta,
  RuleSettingSectionKey,
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
  | "ban_durations_minutes"
  | "full_access_squad_name"
  | "restricted_access_squad_name"
  | "traffic_cap_increment_gb"
  | "traffic_cap_threshold_gb";

type GeneralSettingField = {
  key: GeneralSettingKey;
  inputType: "number" | "boolean" | "number-list" | "text";
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
  { key: "ban_durations_minutes", inputType: "number-list" },
  { key: "full_access_squad_name", inputType: "text" },
  { key: "restricted_access_squad_name", inputType: "text" },
  { key: "traffic_cap_increment_gb", inputType: "number" },
  { key: "traffic_cap_threshold_gb", inputType: "number" }
];

const LIST_SECTIONS = Array.from(
  new Set(RULE_LIST_FIELDS.filter((field) => field.sectionKey !== "access").map((field) => field.sectionKey))
);
const RULES_SECTIONS = ["general", "thresholds", "lists", "providers", "policy", "learning"] as const;
type RulesSection = (typeof RULES_SECTIONS)[number];

function blankProviderProfile(): ProviderProfileDraft {
  return {
    key: "",
    classification: "mixed",
    aliases: [],
    mobile_markers: [],
    home_markers: [],
    asns: []
  };
}

export function RulesPage() {
  const { t, language } = useI18n();
  const { section } = useParams();
  const navigate = useNavigate();
  const activeSection = useMemo<RulesSection>(() => {
    return RULES_SECTIONS.includes(section as RulesSection) ? (section as RulesSection) : "general";
  }, [section]);
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
    if (section && RULES_SECTIONS.includes(section as RulesSection)) {
      return;
    }
    navigate("/rules/general", { replace: true });
  }, [navigate, section]);

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
  const updatedBy = !state?.updated_by || state.updated_by === "bootstrap" ? t("common.system") : state.updated_by;

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

  function providerFieldMeta(field: "key" | "classification" | "aliases" | "mobile_markers" | "home_markers" | "asns") {
    return {
      label: t(`rules.providerProfiles.fields.${field}.label`),
      description: t(`rules.providerProfiles.fields.${field}.description`)
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
      if (field.inputType === "text") {
        payload[field.key] = rawValue.trim();
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

  function serializeProviderProfiles(profiles: ProviderProfileDraft[] | undefined) {
    return (profiles || []).map((profile, index) => {
      const key = profile.key.trim().toLowerCase();
      if (!key) {
        throw new Error(t("rules.providerProfiles.validation.missingKey", { index: index + 1 }));
      }
      const asns = profile.asns
        .map((item) => item.trim())
        .filter(Boolean)
        .map((item) => {
          const parsed = Number(item);
          if (!Number.isFinite(parsed)) {
            throw new Error(
              t("rules.invalidValue", {
                field: providerFieldMeta("asns").label,
                value: item
              })
            );
          }
          return parsed;
        });
      return {
        key,
        classification: profile.classification,
        aliases: profile.aliases.map((item) => item.trim().toLowerCase()).filter(Boolean),
        mobile_markers: profile.mobile_markers.map((item) => item.trim().toLowerCase()).filter(Boolean),
        home_markers: profile.home_markers.map((item) => item.trim().toLowerCase()).filter(Boolean),
        asns
      };
    });
  }

  async function saveRules() {
    if (!draft || !state) return;
    try {
      const payload: Record<string, unknown> = { settings: {} };
      for (const field of RULE_LIST_FIELDS) {
        payload[field.key] = serializeListField(field, draft[field.key]);
      }
      payload.provider_profiles = serializeProviderProfiles(draft.provider_profiles);
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

  function updateProviderProfile(index: number, patch: Partial<ProviderProfileDraft>) {
    setDraft((prev) => {
      const providerProfiles = [...(prev?.provider_profiles || [])];
      providerProfiles[index] = { ...providerProfiles[index], ...patch };
      return {
        ...(prev || {}),
        settings: prev?.settings || {},
        provider_profiles: providerProfiles
      };
    });
    setSaved("");
  }

  function addProviderProfile() {
    setDraft((prev) => ({
      ...(prev || {}),
      settings: prev?.settings || {},
      provider_profiles: [...(prev?.provider_profiles || []), blankProviderProfile()]
    }));
    setSaved("");
  }

  function removeProviderProfile(index: number) {
    setDraft((prev) => ({
      ...(prev || {}),
      settings: prev?.settings || {},
      provider_profiles: (prev?.provider_profiles || []).filter((_, itemIndex) => itemIndex !== index)
    }));
    setSaved("");
  }

  function renderRulesSaveBar() {
    return (
      <div className="panel compact-toolbar">
        <div className="compact-toolbar-main">
          <strong>{t(`layout.subnav.rules.${activeSection}`)}</strong>
          <span className="muted">{t("rules.settingSectionDescription")}</span>
        </div>
        <div className="action-row">
          <span className={dirty ? "tag review-only" : "tag severity-low"}>
            {dirty ? t("common.unsavedChanges") : t("common.saved")}
          </span>
          <button disabled={!dirty} onClick={saveRules}>
            {t("rules.saveRules")}
          </button>
        </div>
      </div>
    );
  }

  function renderGeneralSaveBar() {
    return (
      <div className="panel compact-toolbar">
        <div className="compact-toolbar-main">
          <strong>{t("rules.general.title")}</strong>
          <span className="muted">{t("rules.general.description")}</span>
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
    );
  }

  function renderSettingPanel(title: string, description: string, sectionKeys: RuleSettingSectionKey[]) {
    if (!draft) return null;
    return (
      <div className="panel">
        <div className="panel-heading">
          <h2>{title}</h2>
          <p className="muted">{description}</p>
        </div>
        <div className="form-grid compact-form-grid">
          {RULE_SETTING_FIELDS.filter((field) => sectionKeys.includes(field.sectionKey)).map((field) => {
            const meta = settingFieldMeta(field);
            return (
              <div className="rule-field compact-rule-field" key={field.key}>
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
    );
  }

  function renderGeneralPanel() {
    if (!generalDraft) return null;
    return (
      <div className="panel">
        <div className="panel-heading">
          <h2>{t("rules.general.title")}</h2>
          <p className="muted">{t("rules.general.description")}</p>
        </div>
        {generalError ? <div className="error-box">{generalError}</div> : null}
        {generalSaved ? <div className="ok-box">{generalSaved}</div> : null}
        <div className="form-grid compact-form-grid">
          {GENERAL_SETTINGS_FIELDS.map((field) => {
            const meta = generalFieldMeta(field.key);
            return (
              <div
                className={field.inputType === "number-list" ? "rule-field rule-field-wide compact-rule-field" : "rule-field compact-rule-field"}
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
                    className="note-box compact-note-box"
                    value={generalDraft[field.key] || ""}
                    onChange={(event) => updateGeneralField(field.key, event.target.value)}
                  />
                ) : field.inputType === "text" ? (
                  <input
                    type="text"
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
    );
  }

  function renderListsPanels() {
    if (!draft) return null;
    return LIST_SECTIONS.map((section) => (
      <div className="panel" key={section}>
        <div className="panel-heading">
          <h2>{t(`rulesMeta.sections.${section}`)}</h2>
          <p className="muted">{t("rules.listSectionDescription")}</p>
        </div>
        <div className="detail-grid">
          {RULE_LIST_FIELDS.filter((field) => field.sectionKey === section).map((field) => {
            const meta = listFieldMeta(field);
            return (
              <div className="rule-field compact-rule-field" key={field.key}>
                <FieldLabel
                  label={meta.label}
                  description={meta.description}
                  recommendation={meta.recommendation}
                />
                <textarea
                  className="note-box compact-note-box"
                  value={listValuesToText(draft[field.key])}
                  onChange={(event) => updateListField(field, event.target.value)}
                />
              </div>
            );
          })}
        </div>
      </div>
    ));
  }

  function renderProvidersPanel() {
    if (!draft) return null;
    return (
      <div className="panel">
        <div className="panel-heading panel-heading-row">
          <div>
            <h2>{t("rulesMeta.sections.providers")}</h2>
            <p className="muted">{t("rules.providerProfiles.description")}</p>
          </div>
          <button className="ghost" onClick={addProviderProfile}>
            {t("rules.providerProfiles.add")}
          </button>
        </div>
        <div className="provider-profiles">
          {(draft.provider_profiles || []).map((profile, index) => (
            <div className="provider-card" key={`${profile.key || "provider"}-${index}`}>
              <div className="provider-card-header">
                <div>
                  <strong>{profile.key || t("rules.providerProfiles.cardTitle", { index: index + 1 })}</strong>
                  <p className="muted">{t("rules.providerProfiles.cardSubtitle")}</p>
                </div>
                <button className="ghost small-button" onClick={() => removeProviderProfile(index)}>
                  {t("rules.providerProfiles.remove")}
                </button>
              </div>
              <div className="form-grid compact-form-grid">
                <div className="rule-field compact-rule-field">
                  <FieldLabel label={providerFieldMeta("key").label} description={providerFieldMeta("key").description} />
                  <input value={profile.key} onChange={(event) => updateProviderProfile(index, { key: event.target.value })} />
                </div>
                <div className="rule-field compact-rule-field">
                  <FieldLabel
                    label={providerFieldMeta("classification").label}
                    description={providerFieldMeta("classification").description}
                  />
                  <select
                    value={profile.classification}
                    onChange={(event) =>
                      updateProviderProfile(index, {
                        classification: event.target.value as ProviderProfileDraft["classification"]
                      })
                    }
                  >
                    <option value="mixed">{t("rules.providerProfiles.classifications.mixed")}</option>
                    <option value="mobile">{t("rules.providerProfiles.classifications.mobile")}</option>
                    <option value="home">{t("rules.providerProfiles.classifications.home")}</option>
                  </select>
                </div>
                <div className="rule-field rule-field-wide compact-rule-field">
                  <FieldLabel label={providerFieldMeta("aliases").label} description={providerFieldMeta("aliases").description} />
                  <textarea
                    className="note-box compact-note-box"
                    value={listValuesToText(profile.aliases)}
                    onChange={(event) => updateProviderProfile(index, { aliases: parseListText(event.target.value) })}
                  />
                </div>
                <div className="rule-field compact-rule-field">
                  <FieldLabel
                    label={providerFieldMeta("mobile_markers").label}
                    description={providerFieldMeta("mobile_markers").description}
                  />
                  <textarea
                    className="note-box compact-note-box"
                    value={listValuesToText(profile.mobile_markers)}
                    onChange={(event) => updateProviderProfile(index, { mobile_markers: parseListText(event.target.value) })}
                  />
                </div>
                <div className="rule-field compact-rule-field">
                  <FieldLabel
                    label={providerFieldMeta("home_markers").label}
                    description={providerFieldMeta("home_markers").description}
                  />
                  <textarea
                    className="note-box compact-note-box"
                    value={listValuesToText(profile.home_markers)}
                    onChange={(event) => updateProviderProfile(index, { home_markers: parseListText(event.target.value) })}
                  />
                </div>
                <div className="rule-field rule-field-wide compact-rule-field">
                  <FieldLabel label={providerFieldMeta("asns").label} description={providerFieldMeta("asns").description} />
                  <textarea
                    className="note-box compact-note-box"
                    value={listValuesToText(profile.asns)}
                    onChange={(event) => updateProviderProfile(index, { asns: parseListText(event.target.value) })}
                  />
                </div>
              </div>
            </div>
          ))}
          {(draft.provider_profiles || []).length === 0 ? (
            <div className="provider-empty">
              <span>{t("rules.providerProfiles.empty")}</span>
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  function renderSectionContent() {
    if (!draft && activeSection !== "general") return null;
    if (activeSection === "general") {
      return (
        <>
          {renderGeneralSaveBar()}
          {renderGeneralPanel()}
        </>
      );
    }
    return (
      <>
        {renderRulesSaveBar()}
        {activeSection === "lists" ? renderListsPanels() : null}
        {activeSection === "providers" ? renderProvidersPanel() : null}
        {activeSection === "thresholds"
          ? renderSettingPanel(
              t("rules.sectionTitles.thresholds"),
              t("rules.sectionDescriptions.thresholds"),
              ["thresholds", "scores", "behavior"]
            )
          : null}
        {activeSection === "policy"
          ? renderSettingPanel(
              t("rules.sectionTitles.policy"),
              t("rules.sectionDescriptions.policy"),
              ["policy"]
            )
          : null}
        {activeSection === "learning"
          ? renderSettingPanel(
              t("rules.sectionTitles.learning"),
              t("rules.sectionDescriptions.learning"),
              ["learning"]
            )
          : null}
      </>
    );
  }

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <span className="eyebrow">{t("rules.eyebrow")}</span>
          <h1>{t("rules.title")}</h1>
          <p className="page-lede">{t(`rules.sectionDescriptions.${activeSection}`)}</p>
        </div>
        <span className="chip">{t(`layout.subnav.rules.${activeSection}`)}</span>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      {saved ? <div className="ok-box">{saved}</div> : null}
      {state ? (
        <div className="panel compact-toolbar compact-toolbar-meta">
          <span>{t("rules.revision", { value: state.revision })}</span>
          <span>{t("rules.updatedAt", { value: formatDisplayDateTime(state.updated_at, t("common.notAvailable"), language) })}</span>
          <span>{t("rules.updatedBy", { value: updatedBy })}</span>
        </div>
      ) : null}

      {!draft && !generalDraft ? (
        <div className="detail-grid">
          {Array.from({ length: 3 }).map((_, index) => (
            <div className="panel skeleton-card" key={index}>
              <div className="loading-stack">
                <span className="skeleton-line medium" />
                <span className="skeleton-line long" />
                <span className="skeleton-line long" />
                <span className="skeleton-line short" />
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {renderSectionContent()}
    </section>
  );
}
