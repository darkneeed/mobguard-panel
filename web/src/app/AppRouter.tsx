import { Suspense, lazy, type ComponentType, type ReactElement, useMemo } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { api, BrandingConfig, Session } from "../api/client";
import { PaletteName, ThemeMode } from "./appearance";
import { AppPermission, firstAccessibleRoute, hasPermission } from "./permissions";
import {
  loadAccessPage,
  loadDataPage,
  loadDecisionsPage,
  loadModulesPage,
  loadOverviewPage,
  loadBedolagaPage,
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
const DecisionsPage = lazyNamed(loadDecisionsPage, "DecisionsPage");
const ReviewDetailPage = lazyNamed(loadReviewDetailPage, "ReviewDetailPage");
const RulesPage = lazyNamed(loadRulesPage, "RulesPage");
const TelegramPage = lazyNamed(loadTelegramPage, "TelegramPage");
const AccessPage = lazyNamed(loadAccessPage, "AccessPage");
const DataPage = lazyNamed(loadDataPage, "DataPage");
const QualityPage = lazyNamed(loadQualityPage, "QualityPage");
const BedolagaPage = lazyNamed(loadBedolagaPage, "BedolagaPage");

function RouteFallback() {
  const { t } = useI18n();
  return (
    <div className="panel">
      {t("common.loading")}
    </div>
  );
}

function PermissionRoute({
  session,
  permission,
  children
}: {
  session: Session;
  permission: AppPermission;
  children: ReactElement;
}) {
  if (!hasPermission(session, permission)) {
    return <Navigate to={firstAccessibleRoute(session)} replace />;
  }
  return children;
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
              session={session}
              onLogout={async () => {
                await api.logout().catch(() => undefined);
                setSession(null);
                setState("guest");
              }}
            />
          </Suspense>
        }
      >
        <Route path="/" element={<Navigate to={firstAccessibleRoute(session)} replace />} />
        <Route
          path="/overview"
          element={
            <PermissionRoute session={session} permission="overview.read">
              <OverviewPage session={session} />
            </PermissionRoute>
          }
        />
        <Route
          path="/modules"
          element={
            <PermissionRoute session={session} permission="modules.read">
              <ModulesPage session={session} />
            </PermissionRoute>
          }
        />
        <Route
          path="/queue"
          element={
            <PermissionRoute session={session} permission="reviews.read">
              <ReviewQueuePage session={session} />
            </PermissionRoute>
          }
        />
        <Route
          path="/decisions"
          element={
            <PermissionRoute session={session} permission="data.read">
              <DecisionsPage session={session} />
            </PermissionRoute>
          }
        />
        <Route
          path="/reviews/:caseId"
          element={
            <PermissionRoute session={session} permission="reviews.read">
              <ReviewDetailPage session={session} />
            </PermissionRoute>
          }
        />
        <Route path="/rules" element={<Navigate to="/rules/general" replace />} />
        <Route
          path="/rules/:section"
          element={
            <PermissionRoute session={session} permission="rules.read">
              <RulesPage session={session} />
            </PermissionRoute>
          }
        />
        <Route
          path="/telegram"
          element={
            <PermissionRoute session={session} permission="settings.telegram.read">
              <TelegramPage />
            </PermissionRoute>
          }
        />
        <Route path="/system" element={<Navigate to="/system/access" replace />} />
        <Route
          path="/system/:section"
          element={
            <PermissionRoute session={session} permission="settings.access.read">
              <AccessPage
                branding={branding}
                onBrandingChange={setBranding}
                language={language}
                onLanguageChange={setLanguage}
                palette={palette}
                onPaletteChange={setPalette}
                theme={theme}
                onThemeChange={setTheme}
              />
            </PermissionRoute>
          }
        />
        <Route path="/data" element={<Navigate to="/data/users" replace />} />
        <Route
          path="/data/:section"
          element={
            <PermissionRoute session={session} permission="data.read">
              <DataPage session={session} />
            </PermissionRoute>
          }
        />
        <Route
          path="/quality"
          element={
            <PermissionRoute session={session} permission="quality.read">
              <QualityPage />
            </PermissionRoute>
          }
        />
        <Route
          path="/bedolaga"
          element={
            <PermissionRoute session={session} permission="data.read">
              <BedolagaPage />
            </PermissionRoute>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to={firstAccessibleRoute(session)} replace />} />
    </Routes>
  );
}
