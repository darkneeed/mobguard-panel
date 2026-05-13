import { request } from "../../../shared/api/request";
import { AuthCapabilities, AuthResult, OwnerSecurityStatus, Session, TotpSetupPayload } from "../../../shared/api/types";

export const authApi = {
  authStart: () => request<AuthCapabilities>("/admin/auth/telegram/start", { method: "POST" }),
  authVerify: (payload: Record<string, unknown>) =>
    request<AuthResult>("/admin/auth/telegram/verify", {
      method: "POST",
      body: JSON.stringify({ payload })
    }),
  localLogin: (username: string, password: string) =>
    request<AuthResult>("/admin/auth/local/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    }),
  totpSetup: (challengeToken: string) =>
    request<TotpSetupPayload>("/admin/auth/totp/setup", {
      method: "POST",
      body: JSON.stringify({ challenge_token: challengeToken })
    }),
  totpConfirm: (challengeToken: string, code: string) =>
    request<Session>("/admin/auth/totp/confirm", {
      method: "POST",
      body: JSON.stringify({ challenge_token: challengeToken, code })
    }),
  totpVerify: (challengeToken: string, code: string) =>
    request<Session>("/admin/auth/totp/verify", {
      method: "POST",
      body: JSON.stringify({ challenge_token: challengeToken, code })
    }),
  disableOwnerTotp: () =>
    request<OwnerSecurityStatus>("/admin/auth/totp/disable-all", {
      method: "POST"
    }),
  me: () => request<Session>("/admin/me"),
  logout: () => request<{ ok: boolean }>("/admin/logout", { method: "POST" })
};
