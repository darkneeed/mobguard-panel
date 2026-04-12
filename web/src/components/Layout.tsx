import { useEffect } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { BrandingConfig } from "../api/client";
import { getSecondaryNavigation, primaryNavigation } from "../app/navigation";
import { PaletteName, ThemeMode } from "../app/appearance";
import { prefetchRouteModule } from "../app/routeModules";
import { BrandLogo } from "./BrandLogo";
import { Language, useI18n } from "../localization";

type LayoutProps = {
  branding: BrandingConfig;
  onLogout: () => void;
  username?: string;
  language: Language;
  onLanguageChange: (language: Language) => void;
  palette: PaletteName;
  onPaletteChange: (palette: PaletteName) => void;
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
};

export function Layout({
  branding,
  onLogout,
  username,
  language,
  onLanguageChange,
  palette,
  onPaletteChange,
  theme,
  onThemeChange
}: LayoutProps) {
  const { t } = useI18n();
  const location = useLocation();
  const secondaryNavigation = getSecondaryNavigation(location.pathname);

  useEffect(() => {
    const targets = ["/queue", "/rules/general", "/data/users", "/quality"];
    const browserWindow = window as Window & {
      requestIdleCallback?: (cb: () => void) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    const idle = browserWindow.requestIdleCallback;
    if (idle) {
      const id = idle(() => {
        targets.forEach(prefetchRouteModule);
      });
      return () => browserWindow.cancelIdleCallback?.(id);
    }
    const timer = window.setTimeout(() => {
      targets.forEach(prefetchRouteModule);
    }, 1200);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div className="shell app-shell">
      <aside className="sidebar">
        <Link to="/" className="brand">
          <BrandLogo logoUrl={branding.panel_logo_url} alt={branding.panel_name} />
          <div>
            <strong>{branding.panel_name}</strong>
            <small>{t("layout.brandSubtitle")}</small>
          </div>
        </Link>
        <div className="sidebar-kicker">
          <span className="chip">{t("layout.consoleBadge")}</span>
          <small>{t("layout.consoleDescription")}</small>
        </div>
        {primaryNavigation.map((group) => (
          <div className="sidebar-group" key={group.titleKey}>
            <span className="sidebar-group-title">{t(group.titleKey)}</span>
            <nav className="nav">
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.exact}
                  onMouseEnter={() => prefetchRouteModule(item.to)}
                  onFocus={() => prefetchRouteModule(item.to)}
                >
                  {t(item.labelKey)}
                </NavLink>
              ))}
            </nav>
          </div>
        ))}
        <div className="sidebar-footer">
          <label className="theme-picker">
            <span>{t("layout.language.label")}</span>
            <select value={language} onChange={(event) => onLanguageChange(event.target.value as Language)}>
              <option value="ru">{t("layout.language.ru")}</option>
              <option value="en">{t("layout.language.en")}</option>
            </select>
          </label>
          <label className="theme-picker">
            <span>{t("layout.palette.label")}</span>
            <select value={palette} onChange={(event) => onPaletteChange(event.target.value as PaletteName)}>
              <option value="green">{t("layout.palette.green")}</option>
              <option value="orange">{t("layout.palette.orange")}</option>
              <option value="blue">{t("layout.palette.blue")}</option>
              <option value="purple">{t("layout.palette.purple")}</option>
              <option value="red">{t("layout.palette.red")}</option>
            </select>
          </label>
          <label className="theme-picker">
            <span>{t("layout.theme.label")}</span>
            <select value={theme} onChange={(event) => onThemeChange(event.target.value as ThemeMode)}>
              <option value="system">{t("layout.theme.system")}</option>
              <option value="light">{t("layout.theme.light")}</option>
              <option value="dark">{t("layout.theme.dark")}</option>
            </select>
          </label>
          <span>{username || t("common.admin")}</span>
          <button onClick={onLogout}>{t("layout.logout")}</button>
        </div>
      </aside>
      <div className="content-shell">
        {secondaryNavigation.length > 0 ? (
          <div className="section-tabs">
              {secondaryNavigation.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onMouseEnter={() => prefetchRouteModule(item.to)}
                onFocus={() => prefetchRouteModule(item.to)}
                className={({ isActive }) => `section-tab${isActive ? " active" : ""}`}
              >
                {t(item.labelKey)}
              </NavLink>
            ))}
          </div>
        ) : null}
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
