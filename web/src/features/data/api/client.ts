import { buildSearchParams, request } from "../../../shared/api/request";
import { ReviewListParams } from "../../../shared/api/types";

export const dataApi = {
  searchUsers: (query: string) =>
    request<Record<string, unknown>>(`/admin/data/users/search?query=${encodeURIComponent(query)}`),
  getUserCard: (identifier: string) =>
    request<Record<string, unknown>>(`/admin/data/users/${encodeURIComponent(identifier)}`),
  banUser: (identifier: string, minutes: number) =>
    request<Record<string, unknown>>(`/admin/data/users/${encodeURIComponent(identifier)}/ban`, {
      method: "POST",
      body: JSON.stringify({ minutes })
    }),
  unbanUser: (identifier: string) =>
    request<Record<string, unknown>>(`/admin/data/users/${encodeURIComponent(identifier)}/unban`, {
      method: "POST"
    }),
  updateUserWarnings: (identifier: string, action: string, count = 1) =>
    request<Record<string, unknown>>(`/admin/data/users/${encodeURIComponent(identifier)}/warnings`, {
      method: "POST",
      body: JSON.stringify({ action, count })
    }),
  updateUserStrikes: (identifier: string, action: string, count: number) =>
    request<Record<string, unknown>>(`/admin/data/users/${encodeURIComponent(identifier)}/strikes`, {
      method: "POST",
      body: JSON.stringify({ action, count })
    }),
  updateUserExempt: (identifier: string, kind: string, enabled: boolean) =>
    request<Record<string, unknown>>(`/admin/data/users/${encodeURIComponent(identifier)}/exempt`, {
      method: "POST",
      body: JSON.stringify({ kind, enabled })
    }),
  getViolations: () => request<Record<string, unknown>>("/admin/data/violations"),
  getOverrides: () => request<Record<string, unknown>>("/admin/data/overrides"),
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
  getCache: () => request<Record<string, unknown>>("/admin/data/cache"),
  patchCache: (ip: string, payload: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/admin/data/cache/${encodeURIComponent(ip)}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deleteCache: (ip: string) =>
    request<Record<string, unknown>>(`/admin/data/cache/${encodeURIComponent(ip)}`, {
      method: "DELETE"
    }),
  getLearningAdmin: () => request<Record<string, unknown>>("/admin/data/learning"),
  patchLegacyLearning: (rowId: number, payload: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/admin/data/learning/legacy/${rowId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deleteLegacyLearning: (rowId: number) =>
    request<Record<string, unknown>>(`/admin/data/learning/legacy/${rowId}`, {
      method: "DELETE"
    }),
  listCases: (params: ReviewListParams) =>
    request<Record<string, unknown>>(`/admin/data/cases?${buildSearchParams(params)}`),
  getQuality: () => request<Record<string, unknown>>("/admin/metrics/quality"),
  getHealth: () => request<Record<string, unknown>>("/health")
};
