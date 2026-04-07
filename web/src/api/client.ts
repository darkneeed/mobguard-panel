export type Session = {
  telegram_id: number;
  username?: string;
  first_name?: string;
  expires_at: string;
  payload?: Record<string, unknown>;
};

export type AuthCapabilities = {
  telegram_enabled: boolean;
  bot_username: string;
  local_enabled: boolean;
  local_username_hint: string;
  review_ui_base_url: string;
  panel_name: string;
};

export type EnvFieldState = {
  key: string;
  value: string;
  present: boolean;
  masked: boolean;
  restart_required: boolean;
};

export type ReviewItem = {
  id: number;
  status: string;
  review_reason: string;
  uuid: string | null;
  username: string | null;
  system_id: number | null;
  telegram_id: string | null;
  ip: string;
  tag: string | null;
  verdict: string;
  confidence_band: string;
  score: number;
  isp: string | null;
  asn: number | null;
  punitive_eligible: number;
  severity: "critical" | "high" | "medium" | "low";
  repeat_count: number;
  reason_codes: string[];
  opened_at: string;
  updated_at: string;
  review_url: string;
};

export type ReviewListResponse = {
  items: ReviewItem[];
  count: number;
  page: number;
  page_size: number;
};

export type RulesState = {
  rules: Record<string, unknown>;
  revision: number;
  updated_at: string;
  updated_by: string;
};

export type ReviewListParams = Record<string, string | number | boolean | undefined>;

export type SettingsSectionUpdatePayload = {
  settings?: Record<string, unknown>;
  lists?: Record<string, unknown[]>;
  env?: Record<string, string>;
  revision?: number;
  updated_at?: string;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(data.detail || response.statusText);
  }

  return (await response.json()) as T;
}

export const api = {
  authStart: () =>
    request<AuthCapabilities>(
      "/admin/auth/telegram/start",
      { method: "POST" }
    ),
  authVerify: (payload: Record<string, unknown>) =>
    request<Session>("/admin/auth/telegram/verify", {
      method: "POST",
      body: JSON.stringify({ payload })
    }),
  localLogin: (username: string, password: string) =>
    request<Session>("/admin/auth/local/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    }),
  me: () => request<Session>("/admin/me"),
  logout: () => request<{ ok: boolean }>("/admin/logout", { method: "POST" }),
  listReviews: (params: ReviewListParams) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") {
        search.set(key, String(value));
      }
    });
    return request<ReviewListResponse>(`/admin/reviews?${search.toString()}`);
  },
  getReview: (caseId: string) => request<Record<string, unknown>>(`/admin/reviews/${caseId}`),
  resolveReview: (caseId: string, resolution: string, note: string) =>
    request<Record<string, unknown>>(`/admin/reviews/${caseId}/resolve`, {
      method: "POST",
      body: JSON.stringify({ resolution, note })
    }),
  getRules: () => request<RulesState>("/admin/rules"),
  updateRules: (payload: { rules: Record<string, unknown>; revision: number; updated_at: string }) =>
    request<RulesState>("/admin/rules", {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
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
    }),
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
  listCases: (params: ReviewListParams) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") {
        search.set(key, String(value));
      }
    });
    return request<Record<string, unknown>>(`/admin/data/cases?${search.toString()}`);
  },
  getQuality: () => request<Record<string, unknown>>("/admin/metrics/quality"),
  getHealth: () => request<Record<string, unknown>>("/health")
};
