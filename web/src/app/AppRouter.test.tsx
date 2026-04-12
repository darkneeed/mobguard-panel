import { render, screen } from "@testing-library/react";
import { MemoryRouter, Outlet } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AppRouter } from "./AppRouter";

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
  const baseProps = {
    session: {
      telegram_id: 1,
      username: "operator",
      expires_at: "2026-04-11T00:00:00Z"
    },
    language: "en" as const,
    setLanguage: vi.fn(),
    theme: "system" as const,
    setTheme: vi.fn(),
    setSession: vi.fn(),
    setState: vi.fn()
  };

  it("redirects root to overview", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRouter {...baseProps} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Overview Screen")).toBeInTheDocument();
  });

  it("supports nested rules and data routes", async () => {
    render(
      <MemoryRouter initialEntries={["/rules/policy", "/data/cache"]} initialIndex={0}>
        <AppRouter {...baseProps} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Rules Screen")).toBeInTheDocument();
  });

  it("redirects /rules to the dedicated general tab route", async () => {
    render(
      <MemoryRouter initialEntries={["/rules"]}>
        <AppRouter {...baseProps} />
      </MemoryRouter>
    );

    expect((await screen.findAllByText("Rules Screen")).length).toBeGreaterThan(0);
  });
});
