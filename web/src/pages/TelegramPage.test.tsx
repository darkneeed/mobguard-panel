import { screen, waitFor, cleanup } from "@testing-library/react";
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
    cleanup();
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
        telegram_notify_admin_usage_profile_risk_enabled: true,
        telegram_notify_admin_violation_continues_enabled: true,
        telegram_notify_admin_traffic_limit_exceeded_enabled: true,
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
        admin_review_template: "",
        admin_usage_profile_traffic_template: "",
        admin_usage_profile_devices_template: "",
        admin_usage_profile_connection_template: "",
        admin_violation_continues_template: "",
        admin_traffic_limit_exceeded_template: ""
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
        telegram_notify_admin_usage_profile_risk_enabled: true,
        telegram_notify_admin_violation_continues_enabled: true,
        telegram_notify_admin_traffic_limit_exceeded_enabled: true,
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

  it("renders tabs, switches to templates tab, and saves changed template values", async () => {
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
        telegram_notify_admin_usage_profile_risk_enabled: true,
        telegram_notify_admin_violation_continues_enabled: true,
        telegram_notify_admin_traffic_limit_exceeded_enabled: true,
        telegram_notify_user_warning_only_enabled: true,
        telegram_notify_user_warning_enabled: true,
        telegram_notify_user_ban_enabled: true
      },
      env: {},
      capabilities: {
        admin_bot_enabled: true,
        user_bot_enabled: true
      },
      env_file_path: "/opt/mobguard/.env",
      env_file_writable: true
    });
    vi.mocked(api.getEnforcementSettings).mockResolvedValue({
      settings: {
        user_warning_only_template: "initial-user-warn-only",
        user_warning_template: "initial-user-warn",
        user_ban_template: "",
        admin_warning_only_template: "",
        admin_warning_template: "",
        admin_ban_template: "",
        admin_review_template: "",
        admin_usage_profile_traffic_template: "",
        admin_usage_profile_devices_template: "",
        admin_usage_profile_connection_template: "",
        admin_violation_continues_template: "",
        admin_traffic_limit_exceeded_template: ""
      }
    });
    vi.mocked(api.updateEnforcementSettings).mockResolvedValue({
      settings: {
        user_warning_only_template: "new-user-warn-only-value",
        user_warning_template: "initial-user-warn",
        user_ban_template: "",
        admin_warning_only_template: "",
        admin_warning_template: "",
        admin_ban_template: "",
        admin_review_template: "",
        admin_usage_profile_traffic_template: "",
        admin_usage_profile_devices_template: "",
        admin_usage_profile_connection_template: "",
        admin_violation_continues_template: "",
        admin_traffic_limit_exceeded_template: ""
      }
    });

    const { container } = renderWithProviders(<TelegramPage />);

    // Wait for the data to load and check if we are on the settings tab by default
    await screen.findByText("Admin chat destination");
    expect(screen.queryByText("User messages")).not.toBeInTheDocument();

    // Click on the templates tab
    const templatesTab = screen.getByRole("button", { name: "Templates" });
    await userEvent.click(templatesTab);

    // Verify template panels are displayed
    await screen.findByText("User messages");
    await screen.findByText("Moderator messages");

    // Modify a template value
    const textareas = container.querySelectorAll("textarea");
    expect(textareas.length).toBeGreaterThan(0);
    
    // Clear and type new value
    await userEvent.clear(textareas[0]);
    await userEvent.type(textareas[0], "new-user-warn-only-value");

    // Click "Save message templates"
    const saveButton = screen.getByRole("button", { name: "Save message templates" });
    await userEvent.click(saveButton);

    await waitFor(() => {
      expect(api.updateEnforcementSettings).toHaveBeenCalledWith({
        settings: {
          user_warning_only_template: "new-user-warn-only-value",
          user_warning_template: "initial-user-warn",
          user_ban_template: "",
          admin_warning_only_template: "",
          admin_warning_template: "",
          admin_ban_template: "",
          admin_review_template: "",
          admin_usage_profile_traffic_template: "",
          admin_usage_profile_devices_template: "",
          admin_usage_profile_connection_template: "",
          admin_violation_continues_template: "",
          admin_traffic_limit_exceeded_template: ""
        }
      });
    });
  });
});
