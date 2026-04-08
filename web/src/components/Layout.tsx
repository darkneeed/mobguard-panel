import { Link, NavLink, Outlet } from "react-router-dom";

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

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link to="/" className="brand">
          <span className="brand-mark">MG</span>
          <div>
            <strong>MobGuard</strong>
            <small>{t("layout.brandSubtitle")}</small>
          </div>
        </Link>
        <nav className="nav">
          <NavLink to="/">{t("layout.nav.queue")}</NavLink>
          <NavLink to="/rules">{t("layout.nav.rules")}</NavLink>
          <NavLink to="/telegram">{t("layout.nav.telegram")}</NavLink>
          <NavLink to="/access">{t("layout.nav.access")}</NavLink>
          <NavLink to="/data">{t("layout.nav.data")}</NavLink>
          <NavLink to="/quality">{t("layout.nav.quality")}</NavLink>
        </nav>
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
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
