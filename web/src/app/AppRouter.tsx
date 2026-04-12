import { Suspense, lazy, type ComponentType, useMemo } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { api, BrandingConfig, Session } from "../api/client";
import { PaletteName, ThemeMode } from "./appearance";
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
import { Language, useI18n } from "../localization";

type Props = {
  session: Session;
  language: Language;
  setLanguage: (language: Language) => void;
  branding: BrandingConfig;
  setBranding: (branding: BrandingConfig) => void;
  palette: PaletteName;
  setPalette: (palette: PaletteName) => void;
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
  const { t } = useI18n();
  return (
    <div className="panel">
      {t("common.loading")}
    </div>
  );
}

export function AppRouter({
  session,
  language,
  setLanguage,
  branding,
  setBranding,
  palette,
  setPalette,
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
              branding={branding}
              username={displayName}
              language={language}
              onLanguageChange={setLanguage}
              palette={palette}
              onPaletteChange={setPalette}
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
        <Route
          path="/access"
          element={<AccessPage branding={branding} onBrandingChange={setBranding} />}
        />
        <Route path="/data" element={<Navigate to="/data/users" replace />} />
        <Route path="/data/:section" element={<DataPage />} />
        <Route path="/quality" element={<QualityPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
