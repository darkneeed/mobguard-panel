import { useEffect, useState } from "react";

import { api, AuthCapabilities, BrandingConfig } from "./api/client";
import {
  DEFAULT_BRANDING,
  DEFAULT_PALETTE,
  LANGUAGE_KEY,
  PALETTE_KEY,
  THEME_KEY,
  PaletteName,
  ThemeMode,
} from "./app/appearance";
import { AppRouter } from "./app/AppRouter";
import { useSession } from "./app/useSession";
import { BrandLogo } from "./components/BrandLogo";
import { ToastProvider } from "./components/ToastProvider";
import { LanguageProvider, Language, useI18n } from "./localization";
import { LoginPage } from "./pages/LoginPage";

function LoadingScreen({ branding }: { branding: BrandingConfig }) {
  const { t } = useI18n();
  return (
    <div className="login-screen">
      <div className="login-card loading-card">
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
        <span className="eyebrow">{t("common.loadingLabel")}</span>
        <h1>{t("common.loadingSession")}</h1>
        <div className="loading-stack">
          <span className="skeleton-line long" />
          <span className="skeleton-line medium" />
          <span className="skeleton-line short" />
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const { session, setSession, state, setState } = useSession();
  const [branding, setBranding] = useState<BrandingConfig>(DEFAULT_BRANDING);
  const [bootstrapAuth, setBootstrapAuth] = useState<AuthCapabilities | null>(null);
  const [language, setLanguage] = useState<Language>(() => {
    const stored = window.localStorage.getItem(LANGUAGE_KEY);
    return stored === "en" ? "en" : "ru";
  });
  const [palette, setPalette] = useState<PaletteName>(() => {
    const stored = window.localStorage.getItem(PALETTE_KEY);
    if (stored === "green" || stored === "orange" || stored === "blue" || stored === "purple" || stored === "red") {
      return stored;
    }
    return DEFAULT_PALETTE;
  });
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const stored = window.localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
    return "system";
  });

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const applyTheme = () => {
      const resolved = theme === "system" ? (media.matches ? "dark" : "light") : theme;
      document.documentElement.dataset.theme = resolved;
      document.documentElement.dataset.palette = palette;
    };
    window.localStorage.setItem(THEME_KEY, theme);
    applyTheme();
    media.addEventListener("change", applyTheme);
    return () => media.removeEventListener("change", applyTheme);
  }, [palette, theme]);

  useEffect(() => {
    window.localStorage.setItem(LANGUAGE_KEY, language);
  }, [language]);

  useEffect(() => {
    window.localStorage.setItem(PALETTE_KEY, palette);
  }, [palette]);

  useEffect(() => {
    let cancelled = false;

    async function loadBootstrapAuth() {
      try {
        const payload = await api.authStart();
        if (cancelled) return;
        setBootstrapAuth(payload);
        setBranding({
          panel_name: payload.panel_name || DEFAULT_BRANDING.panel_name,
          panel_logo_url: payload.panel_logo_url || DEFAULT_BRANDING.panel_logo_url,
        });
      } catch {
        if (!cancelled) {
          setBootstrapAuth(null);
        }
      }
    }

    loadBootstrapAuth();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === "loading") {
    return (
      <LanguageProvider language={language} setLanguage={setLanguage}>
        <ToastProvider>
          <LoadingScreen branding={branding} />
        </ToastProvider>
      </LanguageProvider>
    );
  }

  if (!session) {
    return (
      <LanguageProvider language={language} setLanguage={setLanguage}>
        <ToastProvider>
          <LoginPage
            initialAuth={bootstrapAuth}
            branding={branding}
            palette={palette}
            onPaletteChange={setPalette}
            onAuthCapabilitiesLoaded={(payload) => {
              setBootstrapAuth(payload);
              setBranding({
                panel_name: payload.panel_name || DEFAULT_BRANDING.panel_name,
                panel_logo_url: payload.panel_logo_url || DEFAULT_BRANDING.panel_logo_url,
              });
            }}
            onAuthenticated={(nextSession) => {
              setSession(nextSession);
              setState("ready");
            }}
          />
        </ToastProvider>
      </LanguageProvider>
    );
  }

  return (
    <LanguageProvider language={language} setLanguage={setLanguage}>
      <ToastProvider>
        <AppRouter
          session={session}
          language={language}
          setLanguage={setLanguage}
          branding={branding}
          setBranding={setBranding}
          palette={palette}
          setPalette={setPalette}
          theme={theme}
          setTheme={setTheme}
          setSession={setSession}
          setState={setState}
        />
      </ToastProvider>
    </LanguageProvider>
  );
}
