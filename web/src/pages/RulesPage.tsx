import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Loader2 } from "lucide-react";

import {
  api,
  EnforcementSettingsResponse,
  RulesState,
} from "../api/client";
import type { AutomationStatus } from "../api/client";
import { FieldLabel } from "../components/FieldLabel";
import { AsnLookupTool } from "../components/AsnLookupTool";
import { EnforcementPresets } from "../components/EnforcementPresets";
import { RuleListKey } from "../rulesMeta";
import {
  getSettingInputValue,
  listValuesToText,
  normalizeGeneralSettingsDraft,
  normalizeRulesDraft,
  parseListText,
} from "../features/rules/lib/serializers";
import { useI18n } from "../localization";
import {
  automationGuardrailLabels,
  automationModeLabel,
  automationModeReasonLabels,
  deriveAutomationStatus,
} from "../shared/automationStatus";
import {
  ProviderProfileDraft,
  RULE_LIST_FIELDS,
  RULE_SETTING_FIELDS,
  RuleListFieldMeta,
  RuleSettingFieldMeta,
  RuleSettingSectionKey,
  RuleSettingValue,
  RulesDraft,
} from "../rulesMeta";
import { formatDisplayDateTime } from "../utils/datetime";

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
  | "traffic_cap_threshold_gb"
  | "limiter_enabled"
  | "limiter_threshold_count"
  | "limiter_window_seconds"
  | "limiter_cooldown_seconds"
  | "limiter_tolerance"
  | "limiter_tolerance_multiplier"
  | "limiter_ignore_ttl_seconds"
  | "limiter_group_by_subnet"
  | "limiter_group_by_asn"
  | "limiter_rollout_mode"
  | "webhook_enabled"
  | "webhook_urls"
  | "webhook_secret"
  | "webhook_timeout_seconds"
  | "webhook_retry_attempts"
  | "webhook_backoff_seconds";

type GeneralSettingField = {
  key: GeneralSettingKey;
  inputType: "number" | "boolean" | "number-list" | "text" | "choice";
  step?: number;
  choices?: readonly string[];
};

const LIMITER_ROLLOUT_MODE_OPTIONS = [
  "observe",
  "warning_only",
  "enforce",
] as const;

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
  { key: "traffic_cap_threshold_gb", inputType: "number" },
  { key: "limiter_enabled", inputType: "boolean" },
  { key: "limiter_threshold_count", inputType: "number" },
  { key: "limiter_window_seconds", inputType: "number" },
  { key: "limiter_cooldown_seconds", inputType: "number" },
  { key: "limiter_tolerance", inputType: "number" },
  { key: "limiter_tolerance_multiplier", inputType: "number", step: 0.1 },
  { key: "limiter_ignore_ttl_seconds", inputType: "number" },
  { key: "limiter_group_by_subnet", inputType: "boolean" },
  { key: "limiter_group_by_asn", inputType: "boolean" },
  {
    key: "limiter_rollout_mode",
    inputType: "choice",
    choices: LIMITER_ROLLOUT_MODE_OPTIONS,
  },
  { key: "webhook_enabled", inputType: "boolean" },
  { key: "webhook_urls", inputType: "text" },
  { key: "webhook_secret", inputType: "text" },
  { key: "webhook_timeout_seconds", inputType: "number" },
  { key: "webhook_retry_attempts", inputType: "number" },
  { key: "webhook_backoff_seconds", inputType: "number" },
];

const AUTOMATION_GENERAL_FIELD_KEYS = [
  "warning_only_mode",
  "manual_review_mixed_home_enabled",
  "manual_ban_approval_enabled",
  "dry_run",
] as const;
const AUTOMATION_GENERAL_FIELD_SET = new Set<string>(
  AUTOMATION_GENERAL_FIELD_KEYS,
);

const GENERAL_RUNTIME_FIELDS = GENERAL_SETTINGS_FIELDS.filter(
  (field) => !AUTOMATION_GENERAL_FIELD_SET.has(field.key),
);

const AUTOMATION_GENERAL_FIELDS = GENERAL_SETTINGS_FIELDS.filter((field) =>
  AUTOMATION_GENERAL_FIELD_SET.has(field.key),
);
const ADVANCED_AUTOMATION_GENERAL_FIELD_KEYS = [
  "manual_review_mixed_home_enabled",
  "manual_ban_approval_enabled",
] as const;

const POLICY_FIELDS = RULE_SETTING_FIELDS.filter(
  (field) => field.sectionKey === "policy" && field.key !== "shadow_mode",
);

const LIST_SECTIONS = Array.from(
  new Set(
    RULE_LIST_FIELDS.filter((field) => field.sectionKey !== "access").map(
      (field) => field.sectionKey,
    ),
  ),
);
const RULES_SECTIONS = [
  "general",
  "thresholds",
  "lists",
  "providers",
  "learning",
  "retention",
] as const;
type RulesSection = (typeof RULES_SECTIONS)[number];

function blankProviderProfile(): ProviderProfileDraft {
  return {
    key: "",
    classification: "mixed",
    aliases: [],
    mobile_markers: [],
    home_markers: [],
    asns: [],
  };
}

export function RulesPage() {
  const { t, language } = useI18n();
  const { section } = useParams();
  const navigate = useNavigate();
  const activeSection = useMemo<RulesSection>(() => {
    return RULES_SECTIONS.includes(section as RulesSection)
      ? (section as RulesSection)
      : "general";
  }, [section]);
  const [state, setState] = useState<RulesState | null>(null);
  const [draft, setDraft] = useState<RulesDraft | null>(null);
  const [savedDraft, setSavedDraft] = useState<RulesDraft | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [generalDraft, setGeneralDraft] = useState<Record<
    string,
    string
  > | null>(null);
  const [savedGeneralDraft, setSavedGeneralDraft] = useState<Record<
    string,
    string
  > | null>(null);
  const [generalError, setGeneralError] = useState("");
  const [generalSaved, setGeneralSaved] = useState("");
  const [automationError, setAutomationError] = useState("");
  const [automationSaved, setAutomationSaved] = useState("");
  const [policyError, setPolicyError] = useState("");
  const [policySaved, setPolicySaved] = useState("");
  const [rulesSaving, setRulesSaving] = useState(false);
  const [generalSaving, setGeneralSaving] = useState(false);
  const [automationSaving, setAutomationSaving] = useState(false);
  const [policySaving, setPolicySaving] = useState(false);
  const [serverAutomationStatus, setServerAutomationStatus] =
    useState<AutomationStatus | null>(null);

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
          api.getEnforcementSettings(),
        ]);
        if (cancelled) return;

        const typedDetection = detectionPayload as RulesState;
        const normalizedRules = normalizeRulesDraft(typedDetection.rules);
        const typedEnforcement =
          enforcementPayload as EnforcementSettingsResponse;
        const normalizedGeneral = normalizeGeneralSettingsDraft(
          typedEnforcement.settings,
          GENERAL_SETTINGS_FIELDS,
        );

        setState(typedDetection);
        setDraft(normalizedRules);
        setSavedDraft(normalizedRules);
        setGeneralDraft(normalizedGeneral);
        setSavedGeneralDraft(normalizedGeneral);
        setServerAutomationStatus(typedEnforcement.automation_status ?? null);
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
  const generalDirty = GENERAL_RUNTIME_FIELDS.some(
    (field) =>
      (generalDraft?.[field.key] ?? "") !== (savedGeneralDraft?.[field.key] ?? ""),
  );
  const automationGeneralDirty = AUTOMATION_GENERAL_FIELD_KEYS.some(
    (key) => (generalDraft?.[key] ?? "") !== (savedGeneralDraft?.[key] ?? ""),
  );
  const automationModeDirty =
    draft?.settings?.shadow_mode !== savedDraft?.settings?.shadow_mode;
  const policyDirty = POLICY_FIELDS.some(
    (field) =>
      draft?.settings?.[field.key] !== savedDraft?.settings?.[field.key],
  );
  const automationDirty = automationGeneralDirty || automationModeDirty;
  const previewAutomationStatus = useMemo(
    () =>
      deriveAutomationStatus({
        dry_run: generalDraft?.dry_run === "true",
        warning_only_mode: generalDraft?.warning_only_mode === "true",
        manual_review_mixed_home_enabled:
          generalDraft?.manual_review_mixed_home_enabled === "true",
        manual_ban_approval_enabled:
          generalDraft?.manual_ban_approval_enabled === "true",
        shadow_mode: draft?.settings?.shadow_mode === true,
        auto_enforce_requires_hard_or_multi_signal:
          draft?.settings?.auto_enforce_requires_hard_or_multi_signal === true,
        provider_conflict_review_only:
          draft?.settings?.provider_conflict_review_only === true,
      }),
    [draft, generalDraft],
  );
  const automationStatus =
    automationDirty || !serverAutomationStatus
      ? previewAutomationStatus
      : serverAutomationStatus;
  const updatedBy =
    !state?.updated_by || state.updated_by === "bootstrap"
      ? t("common.system")
      : state.updated_by;
  const workMode =
    generalDraft?.dry_run === "true" || draft?.settings?.shadow_mode === true
      ? "observe"
      : "react";
  const reactionMode =
    generalDraft?.warning_only_mode === "true"
      ? "warning_only"
      : "enforce";

  function listFieldMeta(field: RuleListFieldMeta) {
    return {
      label: t(`rulesMeta.listFields.${field.key}.label`),
      description: t(`rulesMeta.listFields.${field.key}.description`),
      recommendation: t(`rulesMeta.listFields.${field.key}.recommendation`),
    };
  }

  function settingFieldMeta(field: RuleSettingFieldMeta) {
    return {
      label: t(`rulesMeta.settingFields.${field.key}.label`),
      description: t(`rulesMeta.settingFields.${field.key}.description`),
      recommendation: t(`rulesMeta.settingFields.${field.key}.recommendation`),
    };
  }

  function generalFieldMeta(key: GeneralSettingKey) {
    return {
      label: t(`rulesMeta.rulesGeneralFields.${key}.label`),
      description: t(`rulesMeta.rulesGeneralFields.${key}.description`),
    };
  }

  function providerFieldMeta(
    field:
      | "key"
      | "classification"
      | "aliases"
      | "mobile_markers"
      | "home_markers"
      | "asns",
  ) {
    return {
      label: t(`rules.providerProfiles.fields.${field}.label`),
      description: t(`rules.providerProfiles.fields.${field}.description`),
    };
  }

  function serializeListField(
    meta: RuleListFieldMeta,
    values: Array<string | number> | undefined,
  ) {
    const rawValues = (values || [])
      .map((item) => String(item).trim())
      .filter(Boolean);
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

  function serializeSettingField(
    meta: RuleSettingFieldMeta,
    value: RuleSettingValue,
  ) {
    if (meta.inputType === "boolean") {
      return Boolean(value);
    }
    if (meta.inputType === "text") {
      return String(value ?? "").trim();
    }
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      throw new Error(
        t("rules.invalidNumber", { field: settingFieldMeta(meta).label }),
      );
    }
    return parsed;
  }

  function serializeGeneralSettings(
    draftValues: Record<string, string>,
    fields: GeneralSettingField[] = GENERAL_SETTINGS_FIELDS,
  ) {
    const payload: Record<string, unknown> = {};
    for (const field of fields) {
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
              throw new Error(
                t("rules.invalidValue", { field: label, value: item }),
              );
            }
            return parsed;
          });
        continue;
      }
      if (field.inputType === "text" || field.inputType === "choice") {
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

  function serializeProviderProfiles(
    profiles: ProviderProfileDraft[] | undefined,
  ) {
    return (profiles || []).map((profile, index) => {
      const key = profile.key.trim().toLowerCase();
      if (!key) {
        throw new Error(
          t("rules.providerProfiles.validation.missingKey", {
            index: index + 1,
          }),
        );
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
                value: item,
              }),
            );
          }
          return parsed;
        });
      return {
        key,
        classification: profile.classification,
        aliases: profile.aliases
          .map((item) => item.trim().toLowerCase())
          .filter(Boolean),
        mobile_markers: profile.mobile_markers
          .map((item) => item.trim().toLowerCase())
          .filter(Boolean),
        home_markers: profile.home_markers
          .map((item) => item.trim().toLowerCase())
          .filter(Boolean),
        asns,
      };
    });
  }

  async function saveRules() {
    if (!draft || !state) return;
    try {
      setRulesSaving(true);
      const payload: Record<string, unknown> = { settings: {} };
      for (const field of RULE_LIST_FIELDS) {
        payload[field.key] = serializeListField(field, draft[field.key]);
      }
      payload.provider_profiles = serializeProviderProfiles(
        draft.provider_profiles,
      );
      for (const field of RULE_SETTING_FIELDS) {
        payload.settings = {
          ...(payload.settings as Record<string, unknown>),
          [field.key]: serializeSettingField(
            field,
            draft.settings?.[field.key],
          ),
        };
      }
      const updated = (await api.updateDetectionSettings({
        rules: payload,
        revision: state.revision,
        updated_at: state.updated_at,
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
    } finally {
      setRulesSaving(false);
    }
  }

  async function saveGeneralSettings() {
    if (!generalDraft) return;
    try {
      setGeneralSaving(true);
      const response = (await api.updateEnforcementSettings({
        settings: serializeGeneralSettings(generalDraft, GENERAL_RUNTIME_FIELDS),
      })) as EnforcementSettingsResponse;
      const normalized = normalizeGeneralSettingsDraft(
        response.settings,
        GENERAL_SETTINGS_FIELDS,
      );
      setGeneralDraft(normalized);
      setSavedGeneralDraft(normalized);
      setGeneralError("");
      setGeneralSaved(t("rules.generalSaved"));
      setServerAutomationStatus(response.automation_status ?? null);
    } catch (err) {
      setGeneralError(
        err instanceof Error ? err.message : t("rules.saveFailed"),
      );
      setGeneralSaved("");
    } finally {
      setGeneralSaving(false);
    }
  }

  function updateListField(meta: RuleListFieldMeta, text: string) {
    setDraft((prev) => ({
      ...(prev || {}),
      [meta.key]: parseListText(text),
      settings: prev?.settings || {},
    }));
    setSaved("");
  }

  function handleAddAsn(listKey: string, asn: number) {
    setDraft((prev) => {
      if (!prev) return null;
      const currentList = prev[listKey as RuleListKey] || [];
      const parsedAsn = Number(asn);
      if (currentList.map(Number).includes(parsedAsn)) return prev;
      return {
        ...prev,
        [listKey]: [...currentList, parsedAsn]
      };
    });
    setSaved("");
  }

  function updateSettingField(meta: RuleSettingFieldMeta, value: string) {
    setDraft((prev) => ({
      ...(prev || {}),
      settings: {
        ...(prev?.settings || {}),
        [meta.key]: meta.inputType === "boolean" ? value === "true" : value,
      },
    }));
    setSaved("");
    setAutomationSaved("");
    setPolicySaved("");
  }

  function updateGeneralField(key: string, value: string) {
    setGeneralDraft((prev) => ({
      ...(prev || {}),
      [key]: value,
    }));
    setGeneralSaved("");
    setAutomationSaved("");
  }

  function updateWorkMode(value: "observe" | "react") {
    setGeneralDraft((prev) => ({
      ...(prev || {}),
      dry_run: value === "observe" ? "true" : "false",
    }));
    setDraft((prev) => ({
      ...(prev || {}),
      settings: {
        ...(prev?.settings || {}),
        shadow_mode: value === "observe",
      },
    }));
    setGeneralSaved("");
    setAutomationSaved("");
    setPolicySaved("");
  }

  function updateReactionMode(value: "warning_only" | "enforce") {
    setGeneralDraft((prev) => ({
      ...(prev || {}),
      warning_only_mode: value === "warning_only" ? "true" : "false",
    }));
    setGeneralSaved("");
    setAutomationSaved("");
  }

  function applyPreset(values: Record<string, string>) {
    Object.entries(values).forEach(([key, val]) => {
      updateGeneralField(key, val);
    });
    const isSoft = values.warning_only_mode === "true";
    updateWorkMode(isSoft ? "observe" : "react");
    updateReactionMode(isSoft ? "warning_only" : "enforce");
  }

  function updateProviderProfile(
    index: number,
    patch: Partial<ProviderProfileDraft>,
  ) {
    setDraft((prev) => {
      const providerProfiles = [...(prev?.provider_profiles || [])];
      providerProfiles[index] = { ...providerProfiles[index], ...patch };
      return {
        ...(prev || {}),
        settings: prev?.settings || {},
        provider_profiles: providerProfiles,
      };
    });
    setSaved("");
  }

  function addProviderProfile() {
    setDraft((prev) => ({
      ...(prev || {}),
      settings: prev?.settings || {},
      provider_profiles: [
        ...(prev?.provider_profiles || []),
        blankProviderProfile(),
      ],
    }));
    setSaved("");
  }

  function removeProviderProfile(index: number) {
    setDraft((prev) => ({
      ...(prev || {}),
      settings: prev?.settings || {},
      provider_profiles: (prev?.provider_profiles || []).filter(
        (_, itemIndex) => itemIndex !== index,
      ),
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
          <button disabled={!dirty || rulesSaving} onClick={saveRules}>
            {rulesSaving && (
              <Loader2 size={14} className="spinner" style={{ marginRight: "6px" }} />
            )}
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
          <span
            className={generalDirty ? "tag review-only" : "tag severity-low"}
          >
            {generalDirty ? t("common.unsavedChanges") : t("common.saved")}
          </span>
          <button disabled={!generalDirty || generalSaving} onClick={saveGeneralSettings}>
            {generalSaving && (
              <Loader2 size={14} className="spinner" style={{ marginRight: "6px" }} />
            )}
            {t("rules.general.save")}
          </button>
        </div>
      </div>
    );
  }

  async function saveAutomationControls() {
    if (!generalDraft || !state) return;
    try {
      setAutomationSaving(true);
      let nextAutomationStatus = serverAutomationStatus;
      if (automationGeneralDirty) {
        const enforcementResponse = (await api.updateEnforcementSettings({
          settings: serializeGeneralSettings(
            generalDraft,
            AUTOMATION_GENERAL_FIELDS,
          ),
        })) as EnforcementSettingsResponse;
        const normalizedGeneral = normalizeGeneralSettingsDraft(
          enforcementResponse.settings,
          GENERAL_SETTINGS_FIELDS,
        );
        nextAutomationStatus = enforcementResponse.automation_status ?? null;
        setGeneralDraft(normalizedGeneral);
        setSavedGeneralDraft(normalizedGeneral);
      }
      if (automationModeDirty) {
        const detectionResponse = (await api.updateDetectionSettings({
          rules: {
            settings: {
              shadow_mode: draft?.settings?.shadow_mode === true,
            },
          },
          revision: state.revision,
          updated_at: state.updated_at,
        })) as RulesState;
        const normalizedRules = normalizeRulesDraft(detectionResponse.rules);
        setState(detectionResponse);
        setDraft(normalizedRules);
        setSavedDraft(normalizedRules);
      }

      setServerAutomationStatus(nextAutomationStatus ?? null);
      setAutomationError("");
      setAutomationSaved(t("rules.automationControls.saved"));
      setError("");
    } catch (err) {
      setAutomationError(
        err instanceof Error ? err.message : t("rules.saveFailed"),
      );
      setAutomationSaved("");
    } finally {
      setAutomationSaving(false);
    }
  }

  async function savePolicySettings() {
    if (!draft || !state) return;
    try {
      setPolicySaving(true);
      const detectionResponse = (await api.updateDetectionSettings({
        rules: {
          settings: Object.fromEntries(
            POLICY_FIELDS.map((field) => [
              field.key,
              serializeSettingField(field, draft.settings?.[field.key]),
            ]),
          ),
        },
        revision: state.revision,
        updated_at: state.updated_at,
      })) as RulesState;
      const normalizedRules = normalizeRulesDraft(detectionResponse.rules);
      setState(detectionResponse);
      setDraft(normalizedRules);
      setSavedDraft(normalizedRules);
      setPolicyError("");
      setPolicySaved(t("rules.policySaved"));
      setSaved("");
    } catch (err) {
      setPolicyError(err instanceof Error ? err.message : t("rules.saveFailed"));
      setPolicySaved("");
    } finally {
      setPolicySaving(false);
    }
  }

  function renderAutomationControlsPanel() {
    if (!generalDraft) return null;
    return (
      <div className="panel" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <div className="panel-heading panel-heading-row" style={{ borderBottom: "1px solid var(--line)", paddingBottom: "1rem" }}>
          <div>
            <h2>{t("rules.automationControls.title")}</h2>
            <p className="muted">{t("rules.automationControls.description")}</p>
          </div>
          <div className="action-row">
            <span
              className={automationDirty ? "tag review-only" : "tag severity-low"}
            >
              {automationDirty ? t("common.unsavedChanges") : t("common.saved")}
            </span>
            <button disabled={!automationDirty || automationSaving} onClick={saveAutomationControls}>
              {automationSaving && (
                <Loader2 size={14} className="spinner" style={{ marginRight: "6px" }} />
              )}
              {t("rules.automationControls.save")}
            </button>
          </div>
        </div>
        {automationError ? <div className="error-box">{automationError}</div> : null}
        {automationSaved ? <div className="ok-box">{automationSaved}</div> : null}

        {/* WORK MODE CARDS SECTOR */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          <div>
            <h3 style={{ fontSize: "0.85rem", textTransform: "uppercase", color: "var(--muted)", marginBottom: "0.6rem", letterSpacing: "0.05em", fontWeight: 600 }}>
              {t("rules.automationControls.workMode.label")}
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem" }}>
              <div
                style={{
                  border: workMode === "observe" ? "2px solid var(--accent)" : "1px solid var(--line)",
                  background: workMode === "observe" ? "var(--accent-soft)" : "rgba(255, 255, 255, 0.01)",
                  borderRadius: "14px",
                  padding: "1.25rem",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.35rem"
                }}
                onClick={() => updateWorkMode("observe")}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ color: "var(--ink)", fontSize: "1.05rem" }}>
                    {t("rules.automationControls.workMode.observe")}
                  </strong>
                  <input
                    type="radio"
                    name="workMode"
                    checked={workMode === "observe"}
                    onChange={() => {}}
                    style={{ pointerEvents: "none" }}
                  />
                </div>
                <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--muted)", lineHeight: "1.4" }}>
                  Режим наблюдения (Shadow Mode). Система анализирует трафик, выставляет баллы и логирует вердикты в фоновом режиме без наложения ограничений на пользователей.
                </p>
              </div>

              <div
                style={{
                  border: workMode === "react" ? "2px solid var(--accent)" : "1px solid var(--line)",
                  background: workMode === "react" ? "var(--accent-soft)" : "rgba(255, 255, 255, 0.01)",
                  borderRadius: "14px",
                  padding: "1.25rem",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.35rem"
                }}
                onClick={() => updateWorkMode("react")}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ color: "var(--ink)", fontSize: "1.05rem" }}>
                    {t("rules.automationControls.workMode.react")}
                  </strong>
                  <input
                    type="radio"
                    name="workMode"
                    checked={workMode === "react"}
                    onChange={() => {}}
                    style={{ pointerEvents: "none" }}
                  />
                </div>
                <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--muted)", lineHeight: "1.4" }}>
                  Активный режим (Enforcement Mode). Система автоматически применяет ограничения к подозрительным подключениям согласно настроенным правилам.
                </p>
              </div>
            </div>
          </div>

          <EnforcementPresets onApply={applyPreset} />

          {/* REACTION MODE SECTOR */}
          <div style={{ opacity: workMode === "react" ? 1 : 0.45, transition: "opacity 0.2s ease" }}>
            <h3 style={{ fontSize: "0.85rem", textTransform: "uppercase", color: "var(--muted)", marginBottom: "0.6rem", letterSpacing: "0.05em", fontWeight: 600 }}>
              {t("rules.automationControls.reactionMode.label")}
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem" }}>
              <div
                style={{
                  border: reactionMode === "enforce" && workMode === "react" ? "2px solid var(--success)" : "1px solid var(--line)",
                  background: reactionMode === "enforce" && workMode === "react" ? "var(--success-soft)" : "rgba(255, 255, 255, 0.01)",
                  borderRadius: "14px",
                  padding: "1.25rem",
                  cursor: workMode === "react" ? "pointer" : "not-allowed",
                  transition: "all 0.2s ease",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.35rem"
                }}
                onClick={() => workMode === "react" && updateReactionMode("enforce")}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ color: "var(--ink)", fontSize: "1.05rem" }}>
                    {t("rules.automationControls.reactionMode.enforce")}
                  </strong>
                  <input
                    type="radio"
                    name="reactionMode"
                    checked={reactionMode === "enforce"}
                    disabled={workMode !== "react"}
                    onChange={() => {}}
                    style={{ pointerEvents: "none" }}
                  />
                </div>
                <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--muted)", lineHeight: "1.4" }}>
                  Жесткая блокировка. Обнаруженные угрозы блокируются сразу, пресекая несанкционированный доступ.
                </p>
              </div>

              <div
                style={{
                  border: reactionMode === "warning_only" && workMode === "react" ? "2px solid var(--warning)" : "1px solid var(--line)",
                  background: reactionMode === "warning_only" && workMode === "react" ? "var(--warning-soft)" : "rgba(255, 255, 255, 0.01)",
                  borderRadius: "14px",
                  padding: "1.25rem",
                  cursor: workMode === "react" ? "pointer" : "not-allowed",
                  transition: "all 0.2s ease",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.35rem"
                }}
                onClick={() => workMode === "react" && updateReactionMode("warning_only")}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ color: "var(--ink)", fontSize: "1.05rem" }}>
                    {t("rules.automationControls.reactionMode.warningOnly")}
                  </strong>
                  <input
                    type="radio"
                    name="reactionMode"
                    checked={reactionMode === "warning_only"}
                    disabled={workMode !== "react"}
                    onChange={() => {}}
                    style={{ pointerEvents: "none" }}
                  />
                </div>
                <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--muted)", lineHeight: "1.4" }}>
                  Только предупреждения. При обнаружении угрозы пользователю высылается предупреждение без блокировки его сессии.
                </p>
              </div>
            </div>
          </div>

          {/* ADVANCED PARAMETERS */}
          <div>
            <h3 style={{ fontSize: "0.85rem", textTransform: "uppercase", color: "var(--muted)", marginBottom: "0.8rem", letterSpacing: "0.05em", fontWeight: 600 }}>
              Дополнительные параметры автоматизации
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem" }}>
              {ADVANCED_AUTOMATION_GENERAL_FIELD_KEYS.map((key) => {
                const meta = generalFieldMeta(key);
                const isTrue = generalDraft[key] === "true";
                return (
                  <div
                    key={key}
                    style={{
                      border: isTrue ? "2px solid var(--accent)" : "1px solid var(--line)",
                      background: isTrue ? "var(--accent-soft)" : "rgba(255, 255, 255, 0.01)",
                      borderRadius: "14px",
                      padding: "1.25rem",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "0.85rem",
                      transition: "all 0.2s ease"
                    }}
                    onClick={() => updateGeneralField(key, isTrue ? "false" : "true")}
                  >
                    <input
                      type="checkbox"
                      checked={isTrue}
                      onChange={() => {}}
                      style={{ marginTop: "0.2rem", pointerEvents: "none" }}
                    />
                    <div>
                      <strong style={{ display: "block", color: "var(--ink)", fontSize: "0.95rem", marginBottom: "0.25rem" }}>
                        {meta.label}
                      </strong>
                      <span style={{ fontSize: "0.8rem", color: "var(--muted)", lineHeight: "1.35", display: "block" }}>
                        {meta.description}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* EMBEDDED REALTIME AUTOMATION STATUS DISPLAY */}
        <div style={{ borderTop: "1px solid var(--line)", paddingTop: "1.25rem" }}>
          {renderAutomationStatusPanel()}
        </div>
      </div>
    );
  }

  function renderPolicyPanel() {
    if (!draft) return null;
    return (
      <div className="panel">
        <div className="panel-heading panel-heading-row">
          <div>
            <h2>{t("rules.sectionTitles.policy")}</h2>
            <p className="muted">{t("rules.sectionDescriptions.policy")}</p>
          </div>
          <div className="action-row">
            <span className={policyDirty ? "tag review-only" : "tag severity-low"}>
              {policyDirty ? t("common.unsavedChanges") : t("common.saved")}
            </span>
            <button disabled={!policyDirty || policySaving} onClick={savePolicySettings}>
              {policySaving && (
                <Loader2 size={14} className="spinner" style={{ marginRight: "6px" }} />
              )}
              {t("rules.saveRules")}
            </button>
          </div>
        </div>
        {policyError ? <div className="error-box">{policyError}</div> : null}
        {policySaved ? <div className="ok-box">{policySaved}</div> : null}
        <div className="form-grid compact-form-grid">
          {POLICY_FIELDS.map((field) => {
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
                    value={getSettingInputValue(
                      field,
                      draft.settings?.[field.key],
                    )}
                    onChange={(event) =>
                      updateSettingField(field, event.target.value)
                    }
                  >
                    <option value="true">{t("common.true")}</option>
                    <option value="false">{t("common.false")}</option>
                  </select>
                ) : (
                  <input
                    type={field.inputType === "number" ? "number" : "text"}
                    step={field.step}
                    value={getSettingInputValue(
                      field,
                      draft.settings?.[field.key],
                    )}
                    onChange={(event) =>
                      updateSettingField(field, event.target.value)
                    }
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  function renderSettingPanel(
    title: string,
    description: string,
    sectionKeys: RuleSettingSectionKey[],
  ) {
    if (!draft) return null;
    return (
      <div className="panel">
        <div className="panel-heading">
          <h2>{title}</h2>
          <p className="muted">{description}</p>
        </div>
        <div className="form-grid compact-form-grid">
          {RULE_SETTING_FIELDS.filter((field) =>
            sectionKeys.includes(field.sectionKey),
          ).map((field) => {
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
                    value={getSettingInputValue(
                      field,
                      draft.settings?.[field.key],
                    )}
                    onChange={(event) =>
                      updateSettingField(field, event.target.value)
                    }
                  >
                    <option value="true">{t("common.true")}</option>
                    <option value="false">{t("common.false")}</option>
                  </select>
                ) : (
                  <input
                    type={field.inputType === "number" ? "number" : "text"}
                    step={field.step}
                    value={getSettingInputValue(
                      field,
                      draft.settings?.[field.key],
                    )}
                    onChange={(event) =>
                      updateSettingField(field, event.target.value)
                    }
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
          {GENERAL_RUNTIME_FIELDS.map((field) => {
            const meta = generalFieldMeta(field.key);
            return (
              <div
                className={
                  field.inputType === "number-list"
                    ? "rule-field rule-field-wide compact-rule-field"
                    : "rule-field compact-rule-field"
                }
                key={field.key}
              >
                <FieldLabel label={meta.label} description={meta.description} />
                {field.inputType === "boolean" ? (
                  <select
                    value={generalDraft[field.key] || "false"}
                    onChange={(event) =>
                      updateGeneralField(field.key, event.target.value)
                    }
                  >
                    <option value="true">{t("common.true")}</option>
                    <option value="false">{t("common.false")}</option>
                  </select>
                ) : field.inputType === "number-list" ? (
                  <textarea
                    className="note-box compact-note-box"
                    value={generalDraft[field.key] || ""}
                    onChange={(event) =>
                      updateGeneralField(field.key, event.target.value)
                    }
                  />
                ) : field.inputType === "choice" ? (
                  <select
                    value={
                      generalDraft[field.key] ||
                      field.choices?.[0] ||
                      ""
                    }
                    onChange={(event) =>
                      updateGeneralField(field.key, event.target.value)
                    }
                  >
                    {(field.choices || []).map((choice) => (
                      <option key={choice} value={choice}>
                        {t(`automationStatus.modes.${choice}` as const)}
                      </option>
                    ))}
                  </select>
                ) : field.inputType === "text" ? (
                  <input
                    type="text"
                    value={generalDraft[field.key] || ""}
                    onChange={(event) =>
                      updateGeneralField(field.key, event.target.value)
                    }
                  />
                ) : (
                  <input
                    type="number"
                    step={field.step}
                    value={generalDraft[field.key] || ""}
                    onChange={(event) =>
                      updateGeneralField(field.key, event.target.value)
                    }
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  function renderAutomationStatusPanel() {
    const modeReasons = automationModeReasonLabels(t, automationStatus);
    const guardrails = automationGuardrailLabels(t, automationStatus);
    return (
      <div className="panel">
        <div className="panel-heading">
          <h2>{t("rules.automationStatus.title")}</h2>
          <p className="muted">{t("rules.automationStatus.description")}</p>
        </div>
        <div className="detail-list">
          <div>
            <dt>{t("rules.automationStatus.modeLabel")}</dt>
            <dd>{automationModeLabel(t, automationStatus)}</dd>
          </div>
          <div>
            <dt>{t("rules.automationStatus.modeReasonsLabel")}</dt>
            <dd>
              {modeReasons.length > 0
                ? modeReasons.join(", ")
                : t("rules.automationStatus.noModeReasons")}
            </dd>
          </div>
          <div>
            <dt>{t("rules.automationStatus.guardrailsLabel")}</dt>
            <dd>
              {guardrails.length > 0
                ? guardrails.join(", ")
                : t("rules.automationStatus.noGuardrails")}
            </dd>
          </div>
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
        {section === "asnLists" && (
          <AsnLookupTool draft={draft} onAddAsn={handleAddAsn} />
        )}
        <div className="detail-grid">
          {RULE_LIST_FIELDS.filter((field) => field.sectionKey === section).map(
            (field) => {
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
                    onChange={(event) =>
                      updateListField(field, event.target.value)
                    }
                  />
                </div>
              );
            },
          )}
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
            <div
              className="provider-card"
              key={`${profile.key || "provider"}-${index}`}
            >
              <div className="provider-card-header">
                <div>
                  <strong>
                    {profile.key ||
                      t("rules.providerProfiles.cardTitle", {
                        index: index + 1,
                      })}
                  </strong>
                  <p className="muted">
                    {t("rules.providerProfiles.cardSubtitle")}
                  </p>
                </div>
                <button
                  className="ghost small-button"
                  onClick={() => removeProviderProfile(index)}
                >
                  {t("rules.providerProfiles.remove")}
                </button>
              </div>
              <div className="form-grid compact-form-grid">
                <div className="rule-field compact-rule-field">
                  <FieldLabel
                    label={providerFieldMeta("key").label}
                    description={providerFieldMeta("key").description}
                  />
                  <input
                    value={profile.key}
                    onChange={(event) =>
                      updateProviderProfile(index, { key: event.target.value })
                    }
                  />
                </div>
                <div className="rule-field compact-rule-field">
                  <FieldLabel
                    label={providerFieldMeta("classification").label}
                    description={
                      providerFieldMeta("classification").description
                    }
                  />
                  <select
                    value={profile.classification}
                    onChange={(event) =>
                      updateProviderProfile(index, {
                        classification: event.target
                          .value as ProviderProfileDraft["classification"],
                      })
                    }
                  >
                    <option value="mixed">
                      {t("rules.providerProfiles.classifications.mixed")}
                    </option>
                    <option value="mobile">
                      {t("rules.providerProfiles.classifications.mobile")}
                    </option>
                    <option value="home">
                      {t("rules.providerProfiles.classifications.home")}
                    </option>
                  </select>
                </div>
                <div className="rule-field rule-field-wide compact-rule-field">
                  <FieldLabel
                    label={providerFieldMeta("aliases").label}
                    description={providerFieldMeta("aliases").description}
                  />
                  <textarea
                    className="note-box compact-note-box"
                    value={listValuesToText(profile.aliases)}
                    onChange={(event) =>
                      updateProviderProfile(index, {
                        aliases: parseListText(event.target.value),
                      })
                    }
                  />
                </div>
                <div className="rule-field compact-rule-field">
                  <FieldLabel
                    label={providerFieldMeta("mobile_markers").label}
                    description={
                      providerFieldMeta("mobile_markers").description
                    }
                  />
                  <textarea
                    className="note-box compact-note-box"
                    value={listValuesToText(profile.mobile_markers)}
                    onChange={(event) =>
                      updateProviderProfile(index, {
                        mobile_markers: parseListText(event.target.value),
                      })
                    }
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
                    onChange={(event) =>
                      updateProviderProfile(index, {
                        home_markers: parseListText(event.target.value),
                      })
                    }
                  />
                </div>
                <div className="rule-field rule-field-wide compact-rule-field">
                  <FieldLabel
                    label={providerFieldMeta("asns").label}
                    description={providerFieldMeta("asns").description}
                  />
                  <textarea
                    className="note-box compact-note-box"
                    value={listValuesToText(profile.asns)}
                    onChange={(event) =>
                      updateProviderProfile(index, {
                        asns: parseListText(event.target.value),
                      })
                    }
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
            {renderAutomationControlsPanel()}
            {renderPolicyPanel()}
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
              ["thresholds", "scores", "behavior"],
            )
          : null}
        {activeSection === "learning"
          ? renderSettingPanel(
              t("rules.sectionTitles.learning"),
              t("rules.sectionDescriptions.learning"),
              ["learning"],
            )
          : null}
        {activeSection === "retention"
          ? renderSettingPanel(
              t("rules.sectionTitles.retention"),
              t("rules.sectionDescriptions.retention"),
              ["retention"],
            )
          : null}
      </>
    );
  }

  return (
    <section className="page">
      <div className="page-header page-header-stack">
        <div>
          <h1>{t("rules.title")}</h1>
          <p className="page-lede">
            {t(`rules.sectionDescriptions.${activeSection}`)}
          </p>
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      {saved ? <div className="ok-box">{saved}</div> : null}
      {state ? (
        <div className="panel compact-toolbar compact-toolbar-meta">
          <span>{t("rules.revision", { value: state.revision })}</span>
          <span>
            {t("rules.updatedAt", {
              value: formatDisplayDateTime(
                state.updated_at,
                t("common.notAvailable"),
                language,
              ),
            })}
          </span>
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
