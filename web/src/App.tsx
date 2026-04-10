import { useEffect, useState } from "react";

import { AppRouter } from "./app/AppRouter";
import { useSession } from "./app/useSession";
import { LanguageProvider, Language, useI18n } from "./localization";
import { LoginPage } from "./pages/LoginPage";

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
  const { session, setSession, state, setState } = useSession();
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
      <AppRouter
        session={session}
        language={language}
        setLanguage={setLanguage}
        theme={theme}
        setTheme={setTheme}
        setSession={setSession}
        setState={setState}
      />
    </LanguageProvider>
  );
}
