import { buildSearchParams, request, requestBlob } from "../../../shared/api/request";
import {
  AnalysisEventListResponse,
  AuditTrailResponse,
  CacheAdminResponse,
  CalibrationExportPreview,
  HealthSnapshot,
  LearningAdminResponse,
  ModuleDetailResponse,
  ModuleListResponse,
  ModuleProvisioningPayload,
  OverviewMetricsResponse,
  OverridesResponse,
  ReviewListParams,
  ReviewListResponse,
  UserCardExportResponse,
  UserCardResponse,
  UserSearchResponse,
  ViolationsResponse
} from "../../../shared/api/types";

export const dataApi = {
  searchUsers: (query: string) =>
    request<UserSearchResponse>(`/admin/data/users/search?query=${encodeURIComponent(query)}`),
  getUserCard: (identifier: string) =>
    request<UserCardResponse>(`/admin/data/users/${encodeURIComponent(identifier)}`),
  getUserCardExport: (identifier: string) =>
    request<UserCardExportResponse>(`/admin/data/users/${encodeURIComponent(identifier)}/export`),
  banUser: (identifier: string, minutes: number) =>
    request<UserCardResponse>(`/admin/data/users/${encodeURIComponent(identifier)}/ban`, {
      method: "POST",
      body: JSON.stringify({ minutes })
    }),
  unbanUser: (identifier: string) =>
    request<UserCardResponse>(`/admin/data/users/${encodeURIComponent(identifier)}/unban`, {
      method: "POST"
    }),
  applyUserTrafficCap: (identifier: string, gigabytes: number) =>
    request<UserCardResponse>(`/admin/data/users/${encodeURIComponent(identifier)}/traffic-cap`, {
      method: "POST",
      body: JSON.stringify({ gigabytes })
    }),
  restoreUserTrafficCap: (identifier: string) =>
    request<UserCardResponse>(`/admin/data/users/${encodeURIComponent(identifier)}/traffic-cap/restore`, {
      method: "POST"
    }),
  updateUserWarnings: (identifier: string, action: string, count = 1) =>
    request<UserCardResponse>(`/admin/data/users/${encodeURIComponent(identifier)}/warnings`, {
      method: "POST",
      body: JSON.stringify({ action, count })
    }),
  updateUserStrikes: (identifier: string, action: string, count: number) =>
    request<UserCardResponse>(`/admin/data/users/${encodeURIComponent(identifier)}/strikes`, {
      method: "POST",
      body: JSON.stringify({ action, count })
    }),
  updateUserExempt: (identifier: string, kind: string, enabled: boolean) =>
    request<UserCardResponse>(`/admin/data/users/${encodeURIComponent(identifier)}/exempt`, {
      method: "POST",
      body: JSON.stringify({ kind, enabled })
    }),
  getViolations: () => request<ViolationsResponse>("/admin/data/violations"),
  getOverrides: () => request<OverridesResponse>("/admin/data/overrides"),
  upsertExactOverride: (ip: string, decision: string, ttl_days = 7) =>
    request<Record<string, unknown>>(`/admin/data/overrides/ip/${encodeURIComponent(ip)}`, {
      method: "PUT",
      body: JSON.stringify({ decision, ttl_days })
    }),
  deleteExactOverride: (ip: string) =>
    request<Record<string, unknown>>(`/admin/data/overrides/ip/${encodeURIComponent(ip)}`, {
      method: "DELETE"
    }),
  upsertUnsureOverride: (ip: string, decision: string) =>
    request<Record<string, unknown>>(`/admin/data/overrides/unsure/${encodeURIComponent(ip)}`, {
      method: "PUT",
      body: JSON.stringify({ decision })
    }),
  deleteUnsureOverride: (ip: string) =>
    request<Record<string, unknown>>(`/admin/data/overrides/unsure/${encodeURIComponent(ip)}`, {
      method: "DELETE"
    }),
  getCache: () => request<CacheAdminResponse>("/admin/data/cache"),
  patchCache: (ip: string, payload: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/admin/data/cache/${encodeURIComponent(ip)}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deleteCache: (ip: string) =>
    request<Record<string, unknown>>(`/admin/data/cache/${encodeURIComponent(ip)}`, {
      method: "DELETE"
    }),
  getLearningAdmin: () => request<LearningAdminResponse>("/admin/data/learning"),
  getAuditTrail: (limit = 100) => request<AuditTrailResponse>(`/admin/data/audit?limit=${limit}`),
  patchLegacyLearning: (rowId: number, payload: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/admin/data/learning/legacy/${rowId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deleteLegacyLearning: (rowId: number) =>
    request<Record<string, unknown>>(`/admin/data/learning/legacy/${rowId}`, {
      method: "DELETE"
    }),
  exportCalibration: (params: Record<string, string | number | boolean | undefined>) =>
    requestBlob(`/admin/data/exports/calibration?${buildSearchParams(params)}`),
  previewCalibration: (params: Record<string, string | number | boolean | undefined>) =>
    request<CalibrationExportPreview>(`/admin/data/exports/calibration/preview?${buildSearchParams(params)}`),
  listCases: (params: ReviewListParams) =>
    request<ReviewListResponse>(`/admin/data/cases?${buildSearchParams(params)}`),
  getAnalysisEvents: (params: Record<string, string | number | boolean | undefined>) =>
    request<AnalysisEventListResponse>(`/admin/data/events?${buildSearchParams(params)}`),
  getQuality: (params: Record<string, string | number | boolean | undefined> = {}) =>
    request<Record<string, unknown>>(`/admin/metrics/quality?${buildSearchParams(params)}`),
  getOverview: () => request<OverviewMetricsResponse>("/admin/metrics/overview"),
  getModules: () => request<ModuleListResponse>("/admin/modules"),
  getModuleDetail: (moduleId: string) =>
    request<ModuleDetailResponse>(`/admin/modules/${encodeURIComponent(moduleId)}`),
  createModule: (payload: ModuleProvisioningPayload) =>
    request<ModuleDetailResponse>("/admin/modules", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateModule: (moduleId: string, payload: ModuleProvisioningPayload) =>
    request<ModuleDetailResponse>(`/admin/modules/${encodeURIComponent(moduleId)}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  revealModuleToken: (moduleId: string) =>
    request<Record<string, unknown>>(`/admin/modules/${encodeURIComponent(moduleId)}/token/reveal`, {
      method: "POST"
    }),
  getHealth: () => request<HealthSnapshot>("/health")
};
