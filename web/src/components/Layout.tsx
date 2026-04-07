import { Link, NavLink, Outlet } from "react-router-dom";

type ThemeMode = "light" | "dark" | "system";

type LayoutProps = {
  onLogout: () => void;
  username?: string;
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
};

export function Layout({ onLogout, username, theme, onThemeChange }: LayoutProps) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <Link to="/" className="brand">
          <span className="brand-mark">MG</span>
          <div>
            <strong>MobGuard</strong>
            <small>Admin panel</small>
          </div>
        </Link>
        <nav className="nav">
          <NavLink to="/">Queue</NavLink>
          <NavLink to="/rules">Detection Rules</NavLink>
          <NavLink to="/enforcement">Enforcement</NavLink>
          <NavLink to="/telegram">Telegram</NavLink>
          <NavLink to="/access">Access</NavLink>
          <NavLink to="/data">Data</NavLink>
          <NavLink to="/quality">Quality</NavLink>
        </nav>
        <div className="sidebar-footer">
          <label className="theme-picker">
            <span>Theme</span>
            <select value={theme} onChange={(event) => onThemeChange(event.target.value as ThemeMode)}>
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </label>
          <span>{username || "Admin"}</span>
          <button onClick={onLogout}>Logout</button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
