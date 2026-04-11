import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { getSecondaryNavigation, primaryNavigation } from "../app/navigation";
import { BrandLogo } from "./BrandLogo";
import { Language, useI18n } from "../localization";

type ThemeMode = "light" | "dark" | "system";

type LayoutProps = {
  onLogout: () => void;
  username?: string;
  language: Language;
  onLanguageChange: (language: Language) => void;
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
};

export function Layout({
  onLogout,
  username,
  language,
  onLanguageChange,
  theme,
  onThemeChange
}: LayoutProps) {
  const { t } = useI18n();
  const location = useLocation();
  const secondaryNavigation = getSecondaryNavigation(location.pathname);

  return (
    <div className="shell app-shell">
      <aside className="sidebar">
        <Link to="/" className="brand">
          <BrandLogo />
          <div>
            <strong>MobGuard</strong>
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
                <NavLink key={item.to} to={item.to} end={item.exact}>
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
