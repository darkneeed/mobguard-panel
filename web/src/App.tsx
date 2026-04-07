import { useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { api, Session } from "./api/client";
import { Layout } from "./components/Layout";
import { AccessPage } from "./pages/AccessPage";
import { DataPage } from "./pages/DataPage";
import { EnforcementPage } from "./pages/EnforcementPage";
import { LoginPage } from "./pages/LoginPage";
import { QualityPage } from "./pages/QualityPage";
import { ReviewDetailPage } from "./pages/ReviewDetailPage";
import { ReviewQueuePage } from "./pages/ReviewQueuePage";
import { RulesPage } from "./pages/RulesPage";
import { TelegramPage } from "./pages/TelegramPage";

type ThemeMode = "light" | "dark" | "system";
const THEME_KEY = "mobguard_theme";

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "guest">("loading");
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

  const displayName = useMemo(
    () => session?.username || session?.first_name || `tg:${session?.telegram_id ?? "?"}`,
    [session]
  );

  if (state === "loading") {
    return <div className="login-screen"><div className="login-card">Loading session…</div></div>;
  }

  if (!session) {
    return (
      <LoginPage
        onAuthenticated={(nextSession) => {
          setSession(nextSession);
          setState("ready");
        }}
      />
    );
  }

  return (
    <Routes>
      <Route
        element={
          <Layout
            username={displayName}
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
        <Route path="/enforcement" element={<EnforcementPage />} />
        <Route path="/telegram" element={<TelegramPage />} />
        <Route path="/access" element={<AccessPage />} />
        <Route path="/data" element={<DataPage />} />
        <Route path="/quality" element={<QualityPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
