import { Suspense, lazy, type ComponentType, useMemo } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { api, Session } from "../api/client";
import {
  loadAccessPage,
  loadDataPage,
  loadModulesPage,
  loadOverviewPage,
  loadQualityPage,
  loadReviewDetailPage,
  loadReviewQueuePage,
  loadRulesPage,
  loadTelegramPage
} from "./routeModules";
import { Layout } from "../components/Layout";
import { Language } from "../localization";

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

function lazyNamed<T extends Record<string, ComponentType<any>>, K extends keyof T>(
  loader: () => Promise<T>,
  key: K
) {
  return lazy(async () => {
    const module = await loader();
    return { default: module[key] };
  });
}

const OverviewPage = lazyNamed(loadOverviewPage, "OverviewPage");
const ModulesPage = lazyNamed(loadModulesPage, "ModulesPage");
const ReviewQueuePage = lazyNamed(loadReviewQueuePage, "ReviewQueuePage");
const ReviewDetailPage = lazyNamed(loadReviewDetailPage, "ReviewDetailPage");
const RulesPage = lazyNamed(loadRulesPage, "RulesPage");
const TelegramPage = lazyNamed(loadTelegramPage, "TelegramPage");
const AccessPage = lazyNamed(loadAccessPage, "AccessPage");
const DataPage = lazyNamed(loadDataPage, "DataPage");
const QualityPage = lazyNamed(loadQualityPage, "QualityPage");

function RouteFallback() {
  return (
    <div className="panel">
      Loading…
    </div>
  );
}

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
          <Suspense fallback={<RouteFallback />}>
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
          </Suspense>
        }
      >
        <Route path="/" element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/modules" element={<ModulesPage />} />
        <Route path="/queue" element={<ReviewQueuePage />} />
        <Route path="/reviews/:caseId" element={<ReviewDetailPage />} />
        <Route path="/rules" element={<Navigate to="/rules/general" replace />} />
        <Route path="/rules/:section" element={<RulesPage />} />
        <Route path="/telegram" element={<TelegramPage />} />
        <Route path="/access" element={<AccessPage />} />
        <Route path="/data" element={<Navigate to="/data/users" replace />} />
        <Route path="/data/:section" element={<DataPage />} />
        <Route path="/quality" element={<QualityPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
