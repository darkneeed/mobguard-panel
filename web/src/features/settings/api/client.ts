import { request } from "../../../shared/api/request";
import { SettingsSectionUpdatePayload } from "../../../shared/api/types";

export const settingsApi = {
  getDetectionSettings: () => request<Record<string, unknown>>("/admin/settings/detection"),
  updateDetectionSettings: (payload: { rules: Record<string, unknown>; revision?: number; updated_at?: string }) =>
    request<Record<string, unknown>>("/admin/settings/detection", {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  getAccessSettings: () => request<Record<string, unknown>>("/admin/settings/access"),
  updateAccessSettings: (payload: SettingsSectionUpdatePayload) =>
    request<Record<string, unknown>>("/admin/settings/access", {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  getTelegramSettings: () => request<Record<string, unknown>>("/admin/settings/telegram"),
  updateTelegramSettings: (payload: SettingsSectionUpdatePayload) =>
    request<Record<string, unknown>>("/admin/settings/telegram", {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  getEnforcementSettings: () => request<Record<string, unknown>>("/admin/settings/enforcement"),
  updateEnforcementSettings: (payload: SettingsSectionUpdatePayload) =>
    request<Record<string, unknown>>("/admin/settings/enforcement", {
      method: "PUT",
      body: JSON.stringify(payload)
    })
};
