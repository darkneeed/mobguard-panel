import { request } from "../../../shared/api/request";
import { AuthCapabilities, Session } from "../../../shared/api/types";

export const authApi = {
  authStart: () => request<AuthCapabilities>("/admin/auth/telegram/start", { method: "POST" }),
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
  logout: () => request<{ ok: boolean }>("/admin/logout", { method: "POST" })
};
