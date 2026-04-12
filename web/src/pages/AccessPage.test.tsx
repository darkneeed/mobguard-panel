import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { AccessPage } from "./AccessPage";
import { renderWithProviders } from "../test/renderWithProviders";

vi.mock("../api/client", () => ({
  api: {
    getAccessSettings: vi.fn(),
    updateAccessSettings: vi.fn()
  }
}));

describe("AccessPage", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const basePayload = {
    revision: 1,
    updated_at: "2026-04-11T00:00:00Z",
    updated_by: "system",
    lists: { admin_tg_ids: [1], exempt_ids: [], exempt_tg_ids: [] },
    settings: {
      panel_name: "MobGuard",
      panel_logo_url: ""
    },
    auth: {
      telegram_enabled: true,
      local_enabled: true,
      local_username_hint: "operator"
    },
    env_file_path: "/opt/mobguard/.env",
    env_file_writable: true
  };

  it("saves only changed env secrets", async () => {
    vi.mocked(api.getAccessSettings).mockResolvedValue({
      ...basePayload,
      env: {
        PANEL_LOCAL_USERNAME: {
          key: "PANEL_LOCAL_USERNAME",
          value: "operator",
          present: true,
          masked: false,
          restart_required: true
        },
        PANEL_LOCAL_PASSWORD: {
          key: "PANEL_LOCAL_PASSWORD",
          value: "se******et",
          present: true,
          masked: true,
          restart_required: true
        }
      },
    });
    vi.mocked(api.updateAccessSettings).mockResolvedValue({
      ...basePayload,
      env: {
        PANEL_LOCAL_USERNAME: {
          key: "PANEL_LOCAL_USERNAME",
          value: "operator",
          present: true,
          masked: false,
          restart_required: true
        },
        PANEL_LOCAL_PASSWORD: {
          key: "PANEL_LOCAL_PASSWORD",
          value: "ne******et",
          present: true,
          masked: true,
          restart_required: true
        }
      },
    });

    renderWithProviders(
      <AccessPage
        branding={{ panel_name: "MobGuard", panel_logo_url: "" }}
        onBrandingChange={() => undefined}
      />
    );

    const secretInput = await screen.findByPlaceholderText("Leave blank to keep the current secret value");
    await userEvent.type(secretInput, "new-secret");
    await userEvent.click(screen.getByRole("button", { name: "Save .env settings" }));

    await waitFor(() => {
      expect(api.updateAccessSettings).toHaveBeenCalledWith({
        env: { PANEL_LOCAL_PASSWORD: "new-secret" }
      });
    });
  });

  it("saves branding through dedicated action", async () => {
    const onBrandingChange = vi.fn();
    vi.mocked(api.getAccessSettings).mockResolvedValue({
      ...basePayload,
      env: {}
    });
    vi.mocked(api.updateAccessSettings).mockResolvedValue({
      ...basePayload,
      settings: {
        panel_name: "Acme Shield",
        panel_logo_url: "https://cdn.example.com/logo.png"
      },
      env: {}
    });

    renderWithProviders(
      <AccessPage
        branding={{ panel_name: "MobGuard", panel_logo_url: "" }}
        onBrandingChange={onBrandingChange}
      />
    );

    const serviceNameInput = await screen.findByRole("textbox", { name: "Service name" });
    const logoUrlInput = screen.getByRole("textbox", { name: "Logo URL" });
    await userEvent.clear(serviceNameInput);
    await userEvent.type(serviceNameInput, "Acme Shield");
    await userEvent.type(logoUrlInput, "https://cdn.example.com/logo.png");
    await userEvent.click(screen.getByRole("button", { name: "Save branding" }));

    await waitFor(() => {
      expect(api.updateAccessSettings).toHaveBeenCalledWith({
        settings: {
          panel_name: "Acme Shield",
          panel_logo_url: "https://cdn.example.com/logo.png"
        }
      });
    });
    expect(onBrandingChange).toHaveBeenCalledWith({
      panel_name: "Acme Shield",
      panel_logo_url: "https://cdn.example.com/logo.png"
    });
  });
});
