import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { api, AuthCapabilities, Session } from "../api/client";

declare global {
  interface Window {
    onTelegramAuth?: (user: Record<string, unknown>) => void;
  }
}

type LoginPageProps = {
  onAuthenticated: (session: Session) => void;
};

export function LoginPage({ onAuthenticated }: LoginPageProps) {
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
        setError(err instanceof Error ? err.message : "Auth failed");
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
  }, [auth, onAuthenticated]);

  async function submitLocalLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    try {
      const session = await api.localLogin(localUsername, localPassword);
      onAuthenticated(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Local auth failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-screen">
      <div className="login-card">
        <span className="eyebrow">Remnawave + MobGuard</span>
        <h1>Веб-панель модерации, данных и runtime-настроек</h1>
        <p>
          Очередь спорных кейсов, data-admin, enforcement и runtime-конфигурация в одной панели.
        </p>
        <div className="login-methods">
          <div className="login-method">
            <strong>Telegram вход</strong>
            <div id="telegram-login-slot" className="telegram-slot" />
            {auth && !auth.telegram_enabled ? <p className="muted">Telegram auth не настроен.</p> : null}
            {!auth && !error ? <p className="muted">Загружаю Telegram auth…</p> : null}
          </div>

          <form className="login-method local-login" onSubmit={submitLocalLogin}>
            <strong>Локальный вход</strong>
            <input
              placeholder="Username"
              value={localUsername}
              onChange={(event) => setLocalUsername(event.target.value)}
              disabled={!auth?.local_enabled}
            />
            <input
              type="password"
              placeholder="Password"
              value={localPassword}
              onChange={(event) => setLocalPassword(event.target.value)}
              disabled={!auth?.local_enabled}
            />
            <button disabled={!auth?.local_enabled || submitting}>
              {submitting ? "Signing in…" : "Login"}
            </button>
            {auth && !auth.local_enabled ? <p className="muted">Local fallback auth не настроен.</p> : null}
          </form>
        </div>
        {error ? <div className="error-box">{error}</div> : null}
      </div>
    </div>
  );
}
