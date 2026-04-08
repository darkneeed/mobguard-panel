import { useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { api, Session } from "./api/client";
import { Layout } from "./components/Layout";
import { LanguageProvider, Language, useI18n } from "./localization";
import { AccessPage } from "./pages/AccessPage";
import { DataPage } from "./pages/DataPage";
import { LoginPage } from "./pages/LoginPage";
import { QualityPage } from "./pages/QualityPage";
import { ReviewDetailPage } from "./pages/ReviewDetailPage";
import { ReviewQueuePage } from "./pages/ReviewQueuePage";
import { RulesPage } from "./pages/RulesPage";
import { TelegramPage } from "./pages/TelegramPage";

type ThemeMode = "light" | "dark" | "system";
const THEME_KEY = "mobguard_theme";
const LANGUAGE_KEY = "mobguard_language";

function LoadingScreen() {
  const { t } = useI18n();
  return (
    <div className="login-screen">
      <div className="login-card">{t("common.loadingSession")}</div>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "guest">("loading");
  const [language, setLanguage] = useState<Language>(() => {
    const stored = window.localStorage.getItem(LANGUAGE_KEY);
    return stored === "en" ? "en" : "ru";
  });
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const stored = window.localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
    return "system";
  });

  useEffect(() => {
    api
      .me()
      .then((payload) => {
        setSession(payload);
        setState("ready");
      })
      .catch(() => {
        setSession(null);
        setState("guest");
      });
  }, []);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const applyTheme = () => {
      const resolved = theme === "system" ? (media.matches ? "dark" : "light") : theme;
      document.documentElement.dataset.theme = resolved;
    };
    window.localStorage.setItem(THEME_KEY, theme);
    applyTheme();
    media.addEventListener("change", applyTheme);
    return () => media.removeEventListener("change", applyTheme);
  }, [theme]);

  useEffect(() => {
    window.localStorage.setItem(LANGUAGE_KEY, language);
  }, [language]);

  const displayName = useMemo(
    () => session?.username || session?.first_name || `tg:${session?.telegram_id ?? "?"}`,
    [session]
  );

  if (state === "loading") {
    return (
      <LanguageProvider language={language} setLanguage={setLanguage}>
        <LoadingScreen />
      </LanguageProvider>
    );
  }

  if (!session) {
    return (
      <LanguageProvider language={language} setLanguage={setLanguage}>
        <LoginPage
          onAuthenticated={(nextSession) => {
            setSession(nextSession);
            setState("ready");
          }}
        />
      </LanguageProvider>
    );
  }

  return (
    <LanguageProvider language={language} setLanguage={setLanguage}>
      <Routes>
        <Route
          element={
            <Layout
              username={displayName}
              language={language}
              onLanguageChange={setLanguage}
              theme={theme}
              onThemeChange={setTheme}
              onLogout={async () => {
                await api.logout().catch(() => undefined);
                setSession(null);
                setState("guest");
              }}
            />
          }
        >
          <Route path="/" element={<ReviewQueuePage />} />
          <Route path="/reviews/:caseId" element={<ReviewDetailPage />} />
          <Route path="/rules" element={<RulesPage />} />
          <Route path="/telegram" element={<TelegramPage />} />
          <Route path="/access" element={<AccessPage />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="/quality" element={<QualityPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </LanguageProvider>
  );
}
