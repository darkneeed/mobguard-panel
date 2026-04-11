import {
  ProviderProfileDraft,
  RULE_LIST_FIELDS,
  RULE_SETTING_FIELDS,
  RuleSettingFieldMeta,
  RuleSettingValue,
  RulesDraft
} from "../../../rulesMeta";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function normalizeRulesDraft(source: Record<string, unknown>): RulesDraft {
  const draft: RulesDraft = { settings: {} };
  const settings = isRecord(source.settings) ? source.settings : {};

  for (const field of RULE_LIST_FIELDS) {
    const rawValue = source[field.key];
    draft[field.key] = Array.isArray(rawValue) ? rawValue.map((item) => String(item)) : [];
  }

  for (const field of RULE_SETTING_FIELDS) {
    const rawValue = settings[field.key];
    if (
      typeof rawValue === "string" ||
      typeof rawValue === "number" ||
      typeof rawValue === "boolean"
    ) {
      draft.settings![field.key] = rawValue;
    }
  }

  draft.provider_profiles = Array.isArray(source.provider_profiles)
    ? source.provider_profiles
        .filter(isRecord)
        .map<ProviderProfileDraft>((item) => ({
          key: String(item.key ?? ""),
          classification:
            item.classification === "home" || item.classification === "mobile"
              ? item.classification
              : "mixed",
          aliases: Array.isArray(item.aliases) ? item.aliases.map((entry) => String(entry)) : [],
          mobile_markers: Array.isArray(item.mobile_markers)
            ? item.mobile_markers.map((entry) => String(entry))
            : [],
          home_markers: Array.isArray(item.home_markers)
            ? item.home_markers.map((entry) => String(entry))
            : [],
          asns: Array.isArray(item.asns) ? item.asns.map((entry) => String(entry)) : []
        }))
    : [];

  return draft;
}

export function normalizeGeneralSettingsDraft(
  source: Record<string, string | number | boolean | string[]>,
  fields: Array<{ key: string; inputType: "number" | "boolean" | "number-list" | "text" }>
): Record<string, string> {
  return Object.fromEntries(
    fields.map((field) => {
      const rawValue = source[field.key];
      if (field.inputType === "number-list") {
        return [field.key, Array.isArray(rawValue) ? rawValue.map((item) => String(item)).join("\n") : ""];
      }
      return [field.key, String(rawValue ?? "")];
    })
  );
}

export function listValuesToText(values: Array<string | number> | undefined): string {
  return (values || []).map((item) => String(item)).join("\n");
}

export function parseListText(text: string): string[] {
  return text
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function getSettingInputValue(meta: RuleSettingFieldMeta, value: RuleSettingValue): string {
  if (meta.inputType === "boolean") {
    return value === true ? "true" : "false";
  }
  return value === undefined || value === null ? "" : String(value);
}
