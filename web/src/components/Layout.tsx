import { useEffect } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { BrandingConfig, Session } from "../api/client";
import { getSecondaryNavigation, primaryNavigation } from "../app/navigation";
import { hasPermission } from "../app/permissions";
import { prefetchRouteModule } from "../app/routeModules";
import { BrandLogo } from "./BrandLogo";
import { useI18n } from "../localization";

type LayoutProps = {
  branding: BrandingConfig;
  onLogout: () => void;
  username?: string;
  session: Session;
};

export function Layout({
  branding,
  onLogout,
  username,
  session,
}: LayoutProps) {
  const { t } = useI18n();
  const location = useLocation();
  const secondaryNavigation = getSecondaryNavigation(location.pathname).filter(
    (item) => !item.permission || hasPermission(session, item.permission),
  );
  const visiblePrimaryNavigation = primaryNavigation
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => !item.permission || hasPermission(session, item.permission),
      ),
    }))
    .filter((group) => group.items.length > 0);

  useEffect(() => {
    const targets = ["/queue", "/decisions", "/system/general", "/data/console", "/data/users", "/quality"];
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
          <BrandLogo
            logoUrl={branding.panel_logo_url}
            alt={branding.panel_name}
          />
          <div className="branding-info">
            <strong>{branding.panel_name}</strong>
            <small>{t("layout.brandSubtitle")}</small>
          </div>
        </Link>
        {visiblePrimaryNavigation.map((group) => (
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
                className={({ isActive }) =>
                  `section-tab${isActive ? " active" : ""}`
                }
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
