import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import {
  api,
  AuthCapabilities,
  AuthResult,
  BrandingConfig,
  Session,
  TotpSetupPayload,
} from "../api/client";
import { PaletteName } from "../app/appearance";
import { BrandLogo } from "../components/BrandLogo";
import { useI18n } from "../localization";

declare global {
  interface Window {
    onTelegramAuth?: (user: Record<string, unknown>) => void;
  }
}

type LoginPageProps = {
  branding: BrandingConfig;
  initialAuth: AuthCapabilities | null;
  palette: PaletteName;
  onAuthCapabilitiesLoaded: (auth: AuthCapabilities) => void;
  onPaletteChange: (palette: PaletteName) => void;
  onAuthenticated: (session: Session) => void;
};

export function LoginPage({
  branding,
  initialAuth,
  palette: _palette,
  onAuthCapabilitiesLoaded,
  onPaletteChange: _onPaletteChange,
  onAuthenticated,
}: LoginPageProps) {
  const { t } = useI18n();
  const [error, setError] = useState("");
  const [auth, setAuth] = useState<AuthCapabilities | null>(initialAuth);
  const [localUsername, setLocalUsername] = useState("");
  const [localPassword, setLocalPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [totpSubmitting, setTotpSubmitting] = useState(false);
  const [challengeToken, setChallengeToken] = useState("");
  const [totpSetupRequired, setTotpSetupRequired] = useState(false);
  const [totpCode, setTotpCode] = useState("");
  const [totpSetupData, setTotpSetupData] = useState<TotpSetupPayload | null>(
    null,
  );

  async function handleAuthResult(result: AuthResult) {
    if (result.requires_totp && result.challenge_token) {
      setChallengeToken(result.challenge_token);
      setTotpSetupRequired(Boolean(result.totp_setup_required));
      setTotpCode("");
      if (result.totp_setup_required) {
        const setupPayload = await api.totpSetup(result.challenge_token);
        setTotpSetupData(setupPayload);
      } else {
        setTotpSetupData(null);
      }
      return;
    }
    onAuthenticated(result as Session);
  }

  useEffect(() => {
    if (initialAuth) {
      setAuth(initialAuth);
      if (initialAuth.local_username_hint) {
        setLocalUsername(initialAuth.local_username_hint);
      }
      return;
    }
    api
      .authStart()
      .then((payload) => {
        setAuth(payload);
        onAuthCapabilitiesLoaded(payload);
        if (payload.local_username_hint) {
          setLocalUsername(payload.local_username_hint);
        }
      })
      .catch((err: Error) => setError(err.message));
  }, [initialAuth, onAuthCapabilitiesLoaded]);

  useEffect(() => {
    if (!auth?.telegram_enabled || !auth.bot_username) return;

    window.onTelegramAuth = async (user) => {
      try {
        const result = await api.authVerify(user);
        await handleAuthResult(result);
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
      const result = await api.localLogin(localUsername, localPassword);
      await handleAuthResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("login.localAuthFailed"));
    } finally {
      setSubmitting(false);
    }
  }

  async function submitTotp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!challengeToken) return;
    setTotpSubmitting(true);
    try {
      const session = totpSetupRequired
        ? await api.totpConfirm(challengeToken, totpCode)
        : await api.totpVerify(challengeToken, totpCode);
      onAuthenticated(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("login.totp.failed"));
    } finally {
      setTotpSubmitting(false);
    }
  }

  function cancelTotp() {
    setChallengeToken("");
    setTotpSetupRequired(false);
    setTotpCode("");
    setTotpSetupData(null);
  }

  return (
    <div className="login-screen">
      <div className="login-card">
        <div className="brand-hero">
          <BrandLogo
            className="brand-hero-mark"
            logoUrl={branding.panel_logo_url}
            alt={branding.panel_name}
          />
          <div>
            <strong>{branding.panel_name}</strong>
            <small>{t("layout.brandSubtitle")}</small>
          </div>
        </div>
        <h1>{t("login.title")}</h1>
        <p>{t("login.description")}</p>
        {challengeToken ? (
          <form className="login-method local-login" onSubmit={submitTotp}>
            <strong>
              {totpSetupRequired
                ? t("login.totp.setupTitle")
                : t("login.totp.verifyTitle")}
            </strong>
            <p className="muted">
              {totpSetupRequired
                ? t("login.totp.setupDescription")
                : t("login.totp.verifyDescription")}
            </p>
            {totpSetupRequired && totpSetupData ? (
              <div className="detail-list">
                <div>
                  <dt>{t("login.totp.secretLabel")}</dt>
                  <dd>{totpSetupData.secret}</dd>
                </div>
                <div>
                  <dt>{t("login.totp.issuerLabel")}</dt>
                  <dd>{totpSetupData.issuer}</dd>
                </div>
                <div>
                  <dt>{t("login.totp.accountLabel")}</dt>
                  <dd>{totpSetupData.account_name}</dd>
                </div>
                <div>
                  <dt>{t("login.totp.uriLabel")}</dt>
                  <dd>{totpSetupData.provisioning_uri}</dd>
                </div>
              </div>
            ) : null}
            <input
              inputMode="numeric"
              placeholder={t("login.totp.codePlaceholder")}
              value={totpCode}
              onChange={(event) => setTotpCode(event.target.value)}
            />
            <div className="action-row">
              <button disabled={totpSubmitting || totpCode.trim().length < 6}>
                {totpSubmitting
                  ? t("login.totp.processing")
                  : totpSetupRequired
                    ? t("login.totp.confirmButton")
                    : t("login.totp.verifyButton")}
              </button>
              <button type="button" className="ghost" onClick={cancelTotp}>
                {t("login.totp.cancelButton")}
              </button>
            </div>
          </form>
        ) : null}
        <div className="login-methods">
          <div className="login-method">
            <strong>{t("login.telegramTitle")}</strong>
            <div id="telegram-login-slot" className="telegram-slot" />
            {auth && !auth.telegram_enabled ? (
              <p className="muted">{t("login.telegramNotConfigured")}</p>
            ) : null}
            {!auth && !error ? (
              <p className="muted">{t("login.telegramLoading")}</p>
            ) : null}
          </div>

          <form
            className="login-method local-login"
            onSubmit={submitLocalLogin}
          >
            <strong>{t("login.localTitle")}</strong>
            <input
              placeholder={t("login.usernamePlaceholder")}
              value={localUsername}
              onChange={(event) => setLocalUsername(event.target.value)}
              disabled={!auth?.local_enabled || Boolean(challengeToken)}
            />
            <input
              type="password"
              placeholder={t("login.passwordPlaceholder")}
              value={localPassword}
              onChange={(event) => setLocalPassword(event.target.value)}
              disabled={!auth?.local_enabled || Boolean(challengeToken)}
            />
            <button
              disabled={
                !auth?.local_enabled || submitting || Boolean(challengeToken)
              }
            >
              {submitting ? t("login.signingIn") : t("login.signIn")}
            </button>
            {auth && !auth.local_enabled ? (
              <p className="muted">{t("login.localNotConfigured")}</p>
            ) : null}
          </form>
        </div>
        {error ? <div className="error-box">{error}</div> : null}
      </div>
    </div>
  );
}
