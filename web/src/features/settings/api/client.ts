import { request } from "../../../shared/api/request";
import {
  AccessSettingsResponse,
  DetectionSettingsResponse,
  EnforcementSettingsResponse,
  SettingsSectionUpdatePayload,
  ConfigHealthResponse,
  AsnLookupResponse
} from "../../../shared/api/types";

export const settingsApi = {
  getDetectionSettings: () => request<DetectionSettingsResponse>("/admin/settings/detection"),
  updateDetectionSettings: (payload: { rules: Record<string, unknown>; revision?: number; updated_at?: string }) =>
    request<DetectionSettingsResponse>("/admin/settings/detection", {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  getAccessSettings: () => request<AccessSettingsResponse>("/admin/settings/access"),
  updateAccessSettings: (payload: SettingsSectionUpdatePayload) =>
    request<AccessSettingsResponse>("/admin/settings/access", {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  getTelegramSettings: () => request<Record<string, unknown>>("/admin/settings/telegram"),
  updateTelegramSettings: (payload: SettingsSectionUpdatePayload) =>
    request<Record<string, unknown>>("/admin/settings/telegram", {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  getEnforcementSettings: () => request<EnforcementSettingsResponse>("/admin/settings/enforcement"),
  updateEnforcementSettings: (payload: SettingsSectionUpdatePayload) =>
    request<EnforcementSettingsResponse>("/admin/settings/enforcement", {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  getConfigHealth: () => request<ConfigHealthResponse>("/admin/settings/config-health"),
  asnLookup: (ip: string, force?: boolean) =>
    request<AsnLookupResponse>("/admin/tools/asn-lookup", {
      method: "POST",
      body: JSON.stringify({ ip, force: force ?? false })
    }),
  getRemnawaveInbounds: (moduleName?: string) =>
    request<{ inbounds: Array<Record<string, any>>; available: boolean }>(
      moduleName
        ? `/admin/tools/remnawave-inbounds?module_name=${encodeURIComponent(moduleName)}`
        : "/admin/tools/remnawave-inbounds"
    )

};

