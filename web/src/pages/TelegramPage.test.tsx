import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { TelegramPage } from "./TelegramPage";
import { renderWithProviders } from "../test/renderWithProviders";

vi.mock("../api/client", () => ({
  api: {
    getTelegramSettings: vi.fn(),
    updateTelegramSettings: vi.fn(),
    getEnforcementSettings: vi.fn(),
    updateEnforcementSettings: vi.fn()
  }
}));

describe("TelegramPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("saves changed telegram env values through the dedicated action", async () => {
    vi.mocked(api.getTelegramSettings).mockResolvedValue({
      settings: {
        tg_admin_chat_id: "",
        tg_topic_id: 0,
        telegram_message_min_interval_seconds: 5,
        telegram_admin_notifications_enabled: true,
        telegram_user_notifications_enabled: true,
        telegram_admin_commands_enabled: true,
        telegram_notify_admin_review_enabled: true,
        telegram_notify_admin_warning_only_enabled: true,
        telegram_notify_admin_warning_enabled: true,
        telegram_notify_admin_ban_enabled: true,
        telegram_notify_user_warning_only_enabled: true,
        telegram_notify_user_warning_enabled: true,
        telegram_notify_user_ban_enabled: true
      },
      env: {
        TG_MAIN_BOT_TOKEN: {
          key: "TG_MAIN_BOT_TOKEN",
          value: "to******en",
          present: true,
          masked: true,
          restart_required: true
        },
        TG_ADMIN_BOT_TOKEN: {
          key: "TG_ADMIN_BOT_TOKEN",
          value: "ad******en",
          present: true,
          masked: true,
          restart_required: true
        },
        TG_ADMIN_BOT_USERNAME: {
          key: "TG_ADMIN_BOT_USERNAME",
          value: "mobguard_admin",
          present: true,
          masked: false,
          restart_required: true
        }
      },
      capabilities: {
        admin_bot_enabled: true,
        user_bot_enabled: true
      },
      env_file_path: "/opt/mobguard/.env",
      env_file_writable: true
    });
    vi.mocked(api.getEnforcementSettings).mockResolvedValue({
      settings: {
        user_warning_only_template: "",
        user_warning_template: "",
        user_ban_template: "",
        admin_warning_only_template: "",
        admin_warning_template: "",
        admin_ban_template: "",
        admin_review_template: ""
      }
    });
    vi.mocked(api.updateTelegramSettings).mockResolvedValue({
      settings: {
        tg_admin_chat_id: "",
        tg_topic_id: 0,
        telegram_message_min_interval_seconds: 5,
        telegram_admin_notifications_enabled: true,
        telegram_user_notifications_enabled: true,
        telegram_admin_commands_enabled: true,
        telegram_notify_admin_review_enabled: true,
        telegram_notify_admin_warning_only_enabled: true,
        telegram_notify_admin_warning_enabled: true,
        telegram_notify_admin_ban_enabled: true,
        telegram_notify_user_warning_only_enabled: true,
        telegram_notify_user_warning_enabled: true,
        telegram_notify_user_ban_enabled: true
      },
      env: {
        TG_MAIN_BOT_TOKEN: {
          key: "TG_MAIN_BOT_TOKEN",
          value: "ne******en",
          present: true,
          masked: true,
          restart_required: true
        },
        TG_ADMIN_BOT_TOKEN: {
          key: "TG_ADMIN_BOT_TOKEN",
          value: "ad******en",
          present: true,
          masked: true,
          restart_required: true
        },
        TG_ADMIN_BOT_USERNAME: {
          key: "TG_ADMIN_BOT_USERNAME",
          value: "mobguard_admin",
          present: true,
          masked: false,
          restart_required: true
        }
      },
      capabilities: {
        admin_bot_enabled: true,
        user_bot_enabled: true
      },
      env_file_path: "/opt/mobguard/.env",
      env_file_writable: true
    });

    renderWithProviders(<TelegramPage />);

    const [firstSecretInput] = await screen.findAllByPlaceholderText(
      "Leave blank to keep the current secret value"
    );
    await userEvent.type(firstSecretInput, "next-token");
    await userEvent.click(screen.getByRole("button", { name: "Save .env settings" }));

    await waitFor(() => {
      expect(api.updateTelegramSettings).toHaveBeenCalledWith({
        env: { TG_MAIN_BOT_TOKEN: "next-token" }
      });
    });
  });
});
