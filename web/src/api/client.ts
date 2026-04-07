export type Session = {
  telegram_id: number;
  username?: string;
  first_name?: string;
  expires_at: string;
  payload?: Record<string, unknown>;
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
    request<{ bot_username: string; review_ui_base_url: string; panel_name: string }>(
      "/admin/auth/telegram/start",
      { method: "POST" }
    ),
  authVerify: (payload: Record<string, unknown>) =>
    request<Session>("/admin/auth/telegram/verify", {
      method: "POST",
      body: JSON.stringify({ payload })
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
  getQuality: () => request<Record<string, unknown>>("/admin/metrics/quality"),
  getHealth: () => request<Record<string, unknown>>("/health")
};
