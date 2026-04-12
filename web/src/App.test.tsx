import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("./api/client", () => ({
  api: {
    authStart: vi.fn().mockResolvedValue({
      telegram_enabled: true,
      bot_username: "adminbot",
      local_enabled: true,
      local_username_hint: "operator",
      review_ui_base_url: "",
      panel_name: "Acme Shield",
      panel_logo_url: "https://cdn.example.com/logo.png"
    })
  }
}));

vi.mock("./app/useSession", () => ({
  useSession: () => ({
    session: null,
    setSession: vi.fn(),
    state: "guest" as const,
    setState: vi.fn()
  })
}));

vi.mock("./app/AppRouter", () => ({
  AppRouter: () => <div>router</div>
}));

vi.mock("./pages/LoginPage", () => ({
  LoginPage: ({ branding, palette, onPaletteChange }: any) => (
    <div>
      <span>{branding.panel_name}</span>
      <span>{palette}</span>
      <button onClick={() => onPaletteChange("purple")}>switch palette</button>
    </div>
  )
}));

describe("App appearance bootstrap", () => {
  beforeEach(() => {
    cleanup();
    window.localStorage.clear();
    delete document.documentElement.dataset.palette;
  });

  it("loads branding and persists palette locally", async () => {
    window.localStorage.setItem("mobguard_palette", "blue");

    render(<App />);

    expect(await screen.findByText("Acme Shield")).toBeInTheDocument();
    expect(screen.getByText("blue")).toBeInTheDocument();
    expect(document.documentElement.dataset.palette).toBe("blue");

    await userEvent.click(screen.getByRole("button", { name: "switch palette" }));

    await waitFor(() => {
      expect(document.documentElement.dataset.palette).toBe("purple");
    });
    expect(window.localStorage.getItem("mobguard_palette")).toBe("purple");
  });
});
