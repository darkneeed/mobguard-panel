import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { AccessPage } from "./AccessPage";
import { renderWithProviders } from "../test/renderWithProviders";

vi.mock("../api/client", () => ({
  api: {
    getAccessSettings: vi.fn(),
    updateAccessSettings: vi.fn(),
    disableOwnerTotp: vi.fn()
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
      panel_logo_url: "",
      remnawave_api_url: ""
    },
    auth: {
      telegram_enabled: true,
      local_enabled: true,
      local_username_hint: "operator"
    },
    owner_security: {
      owner_identity_count: 1,
      enabled_owner_count: 1,
      pending_challenge_count: 0,
      totp_enabled: true
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
        language="en"
        onLanguageChange={() => undefined}
        palette="green"
        onPaletteChange={() => undefined}
        theme="system"
        onThemeChange={() => undefined}
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
        panel_logo_url: "https://cdn.example.com/logo.png",
        remnawave_api_url: ""
      },
      env: {}
    });

    renderWithProviders(
      <AccessPage
        branding={{ panel_name: "MobGuard", panel_logo_url: "" }}
        onBrandingChange={onBrandingChange}
        language="en"
        onLanguageChange={() => undefined}
        palette="green"
        onPaletteChange={() => undefined}
        theme="system"
        onThemeChange={() => undefined}
      />
    );

    const serviceNameInput = await screen.findByRole("textbox", { name: "Service name" });
    const logoUrlInput = screen.getByRole("textbox", { name: "Logo URL" });
    await userEvent.clear(serviceNameInput);
    await userEvent.type(serviceNameInput, "Acme Shield");
    await userEvent.type(logoUrlInput, "https://cdn.example.com/logo.png");
    await userEvent.click(screen.getByRole("button", { name: "Save appearance" }));

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
      panel_logo_url: "https://cdn.example.com/logo.png",
      remnawave_api_url: ""
    });
  });

  it("saves remnawave url through integrations action", async () => {
    const onBrandingChange = vi.fn();
    vi.mocked(api.getAccessSettings).mockResolvedValue({
      ...basePayload,
      env: {}
    });
    vi.mocked(api.updateAccessSettings).mockResolvedValue({
      ...basePayload,
      settings: {
        panel_name: "MobGuard",
        panel_logo_url: "",
        remnawave_api_url: "https://panel.example.com/api"
      },
      env: {}
    });

    renderWithProviders(
      <AccessPage
        branding={{ panel_name: "MobGuard", panel_logo_url: "" }}
        onBrandingChange={onBrandingChange}
        language="en"
        onLanguageChange={() => undefined}
        palette="green"
        onPaletteChange={() => undefined}
        theme="system"
        onThemeChange={() => undefined}
      />
    );

    const remnawaveApiUrlInput = await screen.findByRole("textbox", { name: "Remnawave API URL" });
    await userEvent.type(remnawaveApiUrlInput, "https://panel.example.com/api");
    await userEvent.click(screen.getByRole("button", { name: "Save integrations" }));

    await waitFor(() => {
      expect(api.updateAccessSettings).toHaveBeenCalledWith({
        settings: {
          remnawave_api_url: "https://panel.example.com/api"
        }
      });
    });
    expect(onBrandingChange).toHaveBeenCalledWith({
      panel_name: "MobGuard",
      panel_logo_url: "",
      remnawave_api_url: "https://panel.example.com/api"
    });
  });

  it("disables owner otp through dedicated action", async () => {
    vi.mocked(api.getAccessSettings).mockResolvedValue({
      ...basePayload,
      env: {}
    });
    vi.mocked(api.disableOwnerTotp).mockResolvedValue({
      owner_identity_count: 1,
      enabled_owner_count: 0,
      pending_challenge_count: 0,
      totp_enabled: false
    });

    renderWithProviders(
      <AccessPage
        branding={{ panel_name: "MobGuard", panel_logo_url: "" }}
        onBrandingChange={() => undefined}
        language="en"
        onLanguageChange={() => undefined}
        palette="green"
        onPaletteChange={() => undefined}
        theme="system"
        onThemeChange={() => undefined}
      />
    );

    await userEvent.click(
      await screen.findByRole("button", { name: "Disable OTP for all owners" })
    );

    await waitFor(() => {
      expect(api.disableOwnerTotp).toHaveBeenCalled();
    });
    expect(await screen.findByText("OTP was disabled for all owners")).toBeInTheDocument();
  });
});
