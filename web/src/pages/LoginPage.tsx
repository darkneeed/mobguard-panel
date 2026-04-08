import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { api, AuthCapabilities, Session } from "../api/client";
import { useI18n } from "../localization";

declare global {
  interface Window {
    onTelegramAuth?: (user: Record<string, unknown>) => void;
  }
}

type LoginPageProps = {
  onAuthenticated: (session: Session) => void;
};

export function LoginPage({ onAuthenticated }: LoginPageProps) {
  const { t, language, setLanguage } = useI18n();
  const [error, setError] = useState("");
  const [auth, setAuth] = useState<AuthCapabilities | null>(null);
  const [localUsername, setLocalUsername] = useState("");
  const [localPassword, setLocalPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .authStart()
      .then((payload) => {
        setAuth(payload);
        if (payload.local_username_hint) {
          setLocalUsername(payload.local_username_hint);
        }
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!auth?.telegram_enabled || !auth.bot_username) return;

    window.onTelegramAuth = async (user) => {
      try {
        const session = await api.authVerify(user);
        onAuthenticated(session);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("login.authFailed"));
      }
    };

    const container = document.getElementById("telegram-login-slot");
    if (!container) return;
    container.innerHTML = "";

    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", auth.bot_username);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-userpic", "false");
    script.setAttribute("data-request-access", "write");
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    container.appendChild(script);
  }, [auth, onAuthenticated, t]);

  async function submitLocalLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    try {
      const session = await api.localLogin(localUsername, localPassword);
      onAuthenticated(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("login.localAuthFailed"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-screen">
      <div className="login-card">
        <span className="eyebrow">{t("login.eyebrow")}</span>
        <div className="action-row">
          <label className="theme-picker">
            <span>{t("layout.language.label")}</span>
            <select value={language} onChange={(event) => setLanguage(event.target.value as "ru" | "en")}>
              <option value="ru">{t("layout.language.ru")}</option>
              <option value="en">{t("layout.language.en")}</option>
            </select>
          </label>
        </div>
        <h1>{t("login.title")}</h1>
        <p>{t("login.description")}</p>
        <div className="login-methods">
          <div className="login-method">
            <strong>{t("login.telegramTitle")}</strong>
            <div id="telegram-login-slot" className="telegram-slot" />
            {auth && !auth.telegram_enabled ? <p className="muted">{t("login.telegramNotConfigured")}</p> : null}
            {!auth && !error ? <p className="muted">{t("login.telegramLoading")}</p> : null}
          </div>

          <form className="login-method local-login" onSubmit={submitLocalLogin}>
            <strong>{t("login.localTitle")}</strong>
            <input
              placeholder={t("login.usernamePlaceholder")}
              value={localUsername}
              onChange={(event) => setLocalUsername(event.target.value)}
              disabled={!auth?.local_enabled}
            />
            <input
              type="password"
              placeholder={t("login.passwordPlaceholder")}
              value={localPassword}
              onChange={(event) => setLocalPassword(event.target.value)}
              disabled={!auth?.local_enabled}
            />
            <button disabled={!auth?.local_enabled || submitting}>
              {submitting ? t("login.signingIn") : t("login.signIn")}
            </button>
            {auth && !auth.local_enabled ? <p className="muted">{t("login.localNotConfigured")}</p> : null}
          </form>
        </div>
        {error ? <div className="error-box">{error}</div> : null}
      </div>
    </div>
  );
}
