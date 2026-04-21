import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

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
});
