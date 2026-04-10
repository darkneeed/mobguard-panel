import { useMemo } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { api, Session } from "../api/client";
import { Layout } from "../components/Layout";
import { Language } from "../localization";
import { AccessPage } from "../pages/AccessPage";
import { DataPage } from "../pages/DataPage";
import { QualityPage } from "../pages/QualityPage";
import { ReviewDetailPage } from "../pages/ReviewDetailPage";
import { ReviewQueuePage } from "../pages/ReviewQueuePage";
import { RulesPage } from "../pages/RulesPage";
import { TelegramPage } from "../pages/TelegramPage";

type ThemeMode = "light" | "dark" | "system";

type Props = {
  session: Session;
  language: Language;
  setLanguage: (language: Language) => void;
  theme: ThemeMode;
  setTheme: (theme: ThemeMode) => void;
  setSession: (session: Session | null) => void;
  setState: (state: "loading" | "ready" | "guest") => void;
};

export function AppRouter({
  session,
  language,
  setLanguage,
  theme,
  setTheme,
  setSession,
  setState
}: Props) {
  const displayName = useMemo(
    () => session?.username || session?.first_name || `tg:${session?.telegram_id ?? "?"}`,
    [session]
  );

  return (
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
  );
}
