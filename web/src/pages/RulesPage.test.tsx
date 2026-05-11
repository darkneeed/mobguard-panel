import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { RULE_LIST_FIELDS, RULE_SETTING_FIELDS } from "../rulesMeta";
import { renderWithProviders } from "../test/renderWithProviders";
import { RulesPage } from "./RulesPage";

vi.mock("../api/client", () => ({
  api: {
    getDetectionSettings: vi.fn(),
    getEnforcementSettings: vi.fn(),
    updateDetectionSettings: vi.fn(),
    updateEnforcementSettings: vi.fn()
  }
}));

beforeEach(() => {
  vi.resetAllMocks();
});

afterEach(() => {
  cleanup();
});

function buildRulesPayload() {
  const settings = Object.fromEntries(
    RULE_SETTING_FIELDS.map((field) => [
      field.key,
      field.inputType === "boolean" ? false : field.inputType === "text" ? "https://mobguard.example.com" : 1
    ])
  );
  return {
    revision: 7,
    updated_at: "2026-04-21T10:00:00Z",
    updated_by: "admin",
    rules: {
      ...Object.fromEntries(RULE_LIST_FIELDS.map((field) => [field.key, []])),
      provider_profiles: [],
      settings: {
        ...settings,
        db_cleanup_interval_minutes: 30,
        module_heartbeats_retention_days: 14,
        ingested_raw_events_retention_days: 30,
        ip_history_retention_days: 30,
        orphan_analysis_events_retention_days: 30,
        resolved_review_retention_days: 90,
        learning_promote_asn_min_precision: 0.95,
        learning_promote_combo_min_precision: 0.9
      }
    }
  };
}

describe("RulesPage retention settings", () => {
  it("shows retention fields and saves updated values through detection settings", async () => {
    const detectionPayload = buildRulesPayload();
    vi.mocked(api.getDetectionSettings).mockResolvedValue(detectionPayload);
    vi.mocked(api.getEnforcementSettings).mockResolvedValue({ settings: {} });
    vi.mocked(api.updateDetectionSettings).mockResolvedValue({
      ...detectionPayload,
      rules: {
        ...detectionPayload.rules,
        settings: {
          ...(detectionPayload.rules.settings as Record<string, unknown>),
          db_cleanup_interval_minutes: 45
        }
      }
    });

    renderWithProviders(<RulesPage />, {
      route: "/rules/retention",
      path: "/rules/:section"
    });

    expect(await screen.findByText("Database retention")).toBeInTheDocument();

    const cleanupField = screen.getByText("DB cleanup interval (minutes)").closest(".rule-field");
    expect(cleanupField).not.toBeNull();
    const cleanupInput = within(cleanupField as HTMLElement).getByRole("spinbutton");
    await userEvent.clear(cleanupInput);
    await userEvent.type(cleanupInput, "45");
    await userEvent.click(screen.getByRole("button", { name: "Save rules" }));

    await waitFor(() => {
      expect(api.updateDetectionSettings).toHaveBeenCalled();
    });

    const requestPayload = vi.mocked(api.updateDetectionSettings).mock.calls[0][0];
    expect((requestPayload.rules.settings as Record<string, unknown>).db_cleanup_interval_minutes).toBe(45);
    expect((requestPayload.rules.settings as Record<string, unknown>).resolved_review_retention_days).toBe(90);
    expect(requestPayload.revision).toBe(7);
    expect(requestPayload.updated_at).toBe("2026-04-21T10:00:00Z");
    expect(await screen.findByText("Rules updated")).toBeInTheDocument();
  });

  it("shows the derived automation status on the general section", async () => {
    const detectionPayload = buildRulesPayload();
    vi.mocked(api.getDetectionSettings).mockResolvedValue({
      ...detectionPayload,
      rules: {
        ...detectionPayload.rules,
        settings: {
          ...(detectionPayload.rules.settings as Record<string, unknown>),
          shadow_mode: false,
          provider_conflict_review_only: true,
          auto_enforce_requires_hard_or_multi_signal: true,
        },
      },
    });
    vi.mocked(api.getEnforcementSettings).mockResolvedValue({
      settings: {
        dry_run: true,
        warning_only_mode: false,
        manual_review_mixed_home_enabled: false,
        manual_ban_approval_enabled: false,
      },
    });

    renderWithProviders(<RulesPage />, {
      route: "/rules/general",
      path: "/rules/:section",
    });

    expect(await screen.findByText("Automation status")).toBeInTheDocument();
    expect(screen.getByText("Observe only")).toBeInTheDocument();
    expect(screen.getByText(/dry-run remote actions/)).toBeInTheDocument();
  });

  it("saves automation controls and moved policy settings from the general section", async () => {
    const detectionPayload = buildRulesPayload();
    vi.mocked(api.getDetectionSettings).mockResolvedValue({
      ...detectionPayload,
      rules: {
        ...detectionPayload.rules,
        settings: {
          ...(detectionPayload.rules.settings as Record<string, unknown>),
          shadow_mode: false,
          probable_home_warning_only: false,
          auto_enforce_requires_hard_or_multi_signal: true,
          provider_conflict_review_only: false,
        },
      },
    });
    vi.mocked(api.getEnforcementSettings).mockResolvedValue({
      settings: {
        dry_run: true,
        warning_only_mode: false,
        manual_review_mixed_home_enabled: false,
        manual_ban_approval_enabled: false,
      },
      automation_status: {
        mode: "observe",
        mode_reasons: ["dry_run"],
        flags: {
          dry_run: true,
          warning_only_mode: false,
          manual_review_mixed_home_enabled: false,
          manual_ban_approval_enabled: false,
          shadow_mode: false,
          auto_enforce_requires_hard_or_multi_signal: true,
          provider_conflict_review_only: false,
        },
      },
    });
    vi.mocked(api.updateDetectionSettings).mockResolvedValue({
      ...detectionPayload,
      rules: {
        ...detectionPayload.rules,
        settings: {
          ...(detectionPayload.rules.settings as Record<string, unknown>),
          shadow_mode: true,
          probable_home_warning_only: true,
          auto_enforce_requires_hard_or_multi_signal: true,
          provider_conflict_review_only: false,
        },
      },
    });
    vi.mocked(api.updateEnforcementSettings).mockResolvedValue({
      settings: {
        dry_run: false,
        warning_only_mode: false,
        manual_review_mixed_home_enabled: false,
        manual_ban_approval_enabled: false,
      },
      automation_status: {
        mode: "observe",
        mode_reasons: [],
        flags: {
          dry_run: false,
          warning_only_mode: false,
          manual_review_mixed_home_enabled: false,
          manual_ban_approval_enabled: false,
          shadow_mode: false,
          auto_enforce_requires_hard_or_multi_signal: true,
          provider_conflict_review_only: false,
        },
      },
    });

    renderWithProviders(<RulesPage />, {
      route: "/rules/general",
      path: "/rules/:section",
    });

    const automationHeadings = await screen.findAllByText(
      "Automation controls",
    );
    const automationPanel = automationHeadings.at(-1)?.closest(".panel");
    expect(automationPanel).not.toBeNull();

    const dryRunField = within(automationPanel as HTMLElement)
      .getByText("Dry run")
      .closest(".rule-field");
    expect(dryRunField).not.toBeNull();
    await userEvent.selectOptions(
      within(dryRunField as HTMLElement).getByRole("combobox"),
      "false",
    );

    await userEvent.click(
      within(automationPanel as HTMLElement).getByRole("button", {
        name: "Save automation controls",
      }),
    );

    await waitFor(() => {
      expect(api.updateEnforcementSettings).toHaveBeenCalled();
    });

    expect(api.updateDetectionSettings).not.toHaveBeenCalled();
    expect(
      vi.mocked(api.updateEnforcementSettings).mock.calls.at(-1)?.[0],
    ).toEqual({
      settings: {
        dry_run: false,
        warning_only_mode: false,
        manual_review_mixed_home_enabled: false,
        manual_ban_approval_enabled: false,
      },
    });
    expect(
      await within(automationPanel as HTMLElement).findByText(
        "Automation controls saved",
      ),
    ).toBeInTheDocument();

    const policyPanel = screen
      .getByText("Detection policy")
      .closest(".panel");
    expect(policyPanel).not.toBeNull();

    const shadowField = within(policyPanel as HTMLElement)
      .getByText("Shadow mode")
      .closest(".rule-field");
    expect(shadowField).not.toBeNull();
    await userEvent.selectOptions(
      within(shadowField as HTMLElement).getByRole("combobox"),
      "true",
    );

    const probableHomeField = within(policyPanel as HTMLElement)
      .getByText("Probable home = warning only")
      .closest(".rule-field");
    expect(probableHomeField).not.toBeNull();
    await userEvent.selectOptions(
      within(probableHomeField as HTMLElement).getByRole("combobox"),
      "true",
    );

    await userEvent.click(
      within(policyPanel as HTMLElement).getByRole("button", {
        name: "Save rules",
      }),
    );

    await waitFor(() => {
      expect(api.updateDetectionSettings).toHaveBeenCalled();
    });
    expect(
      vi.mocked(api.updateDetectionSettings).mock.calls.at(-1)?.[0],
    ).toEqual({
      rules: {
        settings: {
          shadow_mode: true,
          probable_home_warning_only: true,
          auto_enforce_requires_hard_or_multi_signal: true,
          provider_conflict_review_only: false,
          review_ui_base_url: "https://mobguard.example.com",
          live_rules_refresh_seconds: 1,
        },
      },
      revision: 7,
      updated_at: "2026-04-21T10:00:00Z",
    });
    expect(
      await within(policyPanel as HTMLElement).findByText(
        "Detection policy saved",
      ),
    ).toBeInTheDocument();
  });
});
