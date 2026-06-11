import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Outlet } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppRouter } from "./AppRouter";
import { LanguageProvider } from "../localization";

vi.mock("../components/Layout", () => ({
  Layout: () => (
    <div data-testid="layout-shell">
      <Outlet />
    </div>
  )
}));

vi.mock("../pages/OverviewPage", () => ({ OverviewPage: () => <div>Overview Screen</div> }));
vi.mock("../pages/ReviewQueuePage", () => ({ ReviewQueuePage: () => <div>Queue Screen</div> }));
vi.mock("../pages/ReviewDetailPage", () => ({ ReviewDetailPage: () => <div>Review Detail Screen</div> }));
vi.mock("../pages/RulesPage", () => ({ RulesPage: () => <div>Rules Screen</div> }));
vi.mock("../pages/TelegramPage", () => ({ TelegramPage: () => <div>Telegram Screen</div> }));
vi.mock("../pages/AccessPage", () => ({ AccessPage: () => <div>Access Screen</div> }));
vi.mock("../pages/DataPage", () => ({ DataPage: () => <div>Data Screen</div> }));
vi.mock("../pages/QualityPage", () => ({ QualityPage: () => <div>Quality Screen</div> }));

describe("AppRouter", () => {
  beforeEach(() => {
    cleanup();
  });

  const baseProps = {
    session: {
      telegram_id: 1,
      username: "operator",
      expires_at: "2026-04-11T00:00:00Z",
      role: "owner",
      permissions: [
        "overview.read",
        "quality.read",
        "reviews.read",
        "reviews.resolve",
        "reviews.recheck",
        "rules.read",
        "rules.write",
        "settings.telegram.read",
        "settings.telegram.write",
        "settings.access.read",
        "settings.access.write",
        "data.read",
        "data.write",
        "modules.read",
        "modules.write",
        "modules.token_reveal",
        "audit.read"
      ]
    },
    language: "en" as const,
    setLanguage: vi.fn(),
    branding: {
      panel_name: "MobGuard",
      panel_logo_url: ""
    },
    setBranding: vi.fn(),
    palette: "green" as const,
    setPalette: vi.fn(),
    theme: "system" as const,
    setTheme: vi.fn(),
    setSession: vi.fn(),
    setState: vi.fn()
  };

  it("redirects root to overview", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <LanguageProvider language="en" setLanguage={() => undefined}>
          <AppRouter {...baseProps} />
        </LanguageProvider>
      </MemoryRouter>
    );

    expect((await screen.findAllByText("Overview Screen")).length).toBeGreaterThan(0);
  });

  it("supports nested rules and data routes", async () => {
    render(
      <MemoryRouter initialEntries={["/system/general", "/data/cache"]} initialIndex={0}>
        <LanguageProvider language="en" setLanguage={() => undefined}>
          <AppRouter {...baseProps} />
        </LanguageProvider>
      </MemoryRouter>
    );

    expect(await screen.findByText("Rules Screen")).toBeInTheDocument();
  });

  it("redirects /system to the dedicated access tab route", async () => {
    render(
      <MemoryRouter initialEntries={["/system"]}>
        <LanguageProvider language="en" setLanguage={() => undefined}>
          <AppRouter {...baseProps} />
        </LanguageProvider>
      </MemoryRouter>
    );

    expect((await screen.findAllByText("Access Screen")).length).toBeGreaterThan(0);
  });

  it("redirects a viewer away from owner-only routes", async () => {
    render(
      <MemoryRouter initialEntries={["/rules/policy"]}>
        <LanguageProvider language="en" setLanguage={() => undefined}>
          <AppRouter
            {...baseProps}
            session={{
              telegram_id: 3,
              username: "viewer",
              expires_at: "2026-04-11T00:00:00Z",
              role: "viewer",
              permissions: ["overview.read", "quality.read", "reviews.read", "data.read", "modules.read", "audit.read"]
            }}
          />
        </LanguageProvider>
      </MemoryRouter>
    );

    expect(await screen.findByText("Overview Screen")).toBeInTheDocument();
  });
});
