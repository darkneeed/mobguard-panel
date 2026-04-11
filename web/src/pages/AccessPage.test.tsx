import { screen, waitFor } from "@testing-library/react";
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
    vi.clearAllMocks();
  });

  it("saves only changed env secrets", async () => {
    vi.mocked(api.getAccessSettings).mockResolvedValue({
      revision: 1,
      updated_at: "2026-04-11T00:00:00Z",
      updated_by: "system",
      lists: { admin_tg_ids: [1], exempt_ids: [], exempt_tg_ids: [] },
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
      auth: {
        telegram_enabled: true,
        local_enabled: true,
        local_username_hint: "operator"
      },
      env_file_path: "/opt/mobguard/.env",
      env_file_writable: true
    });
    vi.mocked(api.updateAccessSettings).mockResolvedValue({
      revision: 1,
      updated_at: "2026-04-11T00:00:00Z",
      updated_by: "system",
      lists: { admin_tg_ids: [1], exempt_ids: [], exempt_tg_ids: [] },
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
      auth: {
        telegram_enabled: true,
        local_enabled: true,
        local_username_hint: "operator"
      },
      env_file_path: "/opt/mobguard/.env",
      env_file_writable: true
    });

    renderWithProviders(<AccessPage />);

    const secretInput = await screen.findByPlaceholderText("Leave blank to keep the current secret value");
    await userEvent.type(secretInput, "new-secret");
    await userEvent.click(screen.getByRole("button", { name: "Save .env settings" }));

    await waitFor(() => {
      expect(api.updateAccessSettings).toHaveBeenCalledWith({
        env: { PANEL_LOCAL_PASSWORD: "new-secret" }
      });
    });
  });
});
