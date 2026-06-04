import { AutomationStatus } from "./api/types";

type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

type AutomationFlagsInput = Partial<{
  dry_run: boolean;
  warning_only_mode: boolean;
  manual_review_mixed_home_enabled: boolean;
  manual_ban_approval_enabled: boolean;
  shadow_mode: boolean;
  auto_enforce_requires_hard_or_multi_signal: boolean;
  provider_conflict_review_only: boolean;
}>;

const MODE_REASON_KEYS = ["dry_run", "shadow_mode", "warning_only_mode"] as const;
const GUARDRAIL_KEYS = [
  "auto_enforce_requires_hard_or_multi_signal",
  "provider_conflict_review_only",
  "manual_review_mixed_home_enabled",
  "manual_ban_approval_enabled",
] as const;

export function deriveAutomationStatus(flagsInput: AutomationFlagsInput): AutomationStatus {
  const flags = {
    dry_run: Boolean(flagsInput.dry_run),
    warning_only_mode: Boolean(flagsInput.warning_only_mode),
    manual_review_mixed_home_enabled: Boolean(flagsInput.manual_review_mixed_home_enabled),
    manual_ban_approval_enabled: Boolean(flagsInput.manual_ban_approval_enabled),
    shadow_mode: Boolean(flagsInput.shadow_mode),
    auto_enforce_requires_hard_or_multi_signal: Boolean(flagsInput.auto_enforce_requires_hard_or_multi_signal),
    provider_conflict_review_only: Boolean(flagsInput.provider_conflict_review_only),
  };
  const mode_reasons = MODE_REASON_KEYS.filter((key) => flags[key]);
  const mode: AutomationStatus["mode"] =
    flags.dry_run || flags.shadow_mode
      ? "observe"
      : flags.warning_only_mode
        ? "warning_only"
        : "enforce";
  return { mode, mode_reasons: [...mode_reasons], flags };
}

export function automationModeLabel(t: TranslateFn, status: AutomationStatus | null | undefined): string {
  const mode = status?.mode || "observe";
  return t(`automationStatus.modes.${mode}`);
}

function _fallbackReasonLabel(reason: string): string {
  return reason.replace(/_/g, " ");
}

export function automationModeReasonLabels(t: TranslateFn, status: AutomationStatus | null | undefined): string[] {
  return (status?.mode_reasons || []).map((reason) => {
    const key = `automationStatus.reasons.${reason}`;
    const translated = t(key);
    return translated === key ? _fallbackReasonLabel(reason) : translated;
  });
}

export function automationGuardrailLabels(t: TranslateFn, status: AutomationStatus | null | undefined): string[] {
  const flags = status?.flags || {};
  return GUARDRAIL_KEYS.filter((key) => Boolean(flags[key])).map((key) => {
    const translationKey = `automationStatus.flags.${key}`;
    const translated = t(translationKey);
    return translated === translationKey ? _fallbackReasonLabel(key) : translated;
  });
}
