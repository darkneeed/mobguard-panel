import { EnvFieldState } from "../../../shared/api/types";

export function buildInitialEnvDraft(fields: Record<string, EnvFieldState> | undefined): Record<string, string> {
  return Object.fromEntries(
    Object.entries(fields || {}).map(([key, field]) => [key, field.masked ? "" : field.value])
  );
}

export function buildEnvUpdates(
  fields: Record<string, EnvFieldState> | undefined,
  draft: Record<string, string>
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(fields || {})
      .filter(([key, field]) => {
        const nextValue = draft[key] ?? "";
        if (field.masked) {
          return nextValue.trim() !== "";
        }
        return nextValue !== field.value;
      })
      .map(([key]) => [key, draft[key] ?? ""])
  );
}

export function isEnvDirty(
  fields: Record<string, EnvFieldState> | undefined,
  draft: Record<string, string>
): boolean {
  return Object.keys(buildEnvUpdates(fields, draft)).length > 0;
}
