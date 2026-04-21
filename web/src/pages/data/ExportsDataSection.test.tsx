import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ExportsDataSection } from "./ExportsDataSection";

const t = (key: string) => key;

describe("ExportsDataSection", () => {
  it("renders readiness snapshot from preview manifest", () => {
    render(
      <ExportsDataSection
        t={t}
        isPending={() => false}
        calibrationFilters={{
          opened_from: "",
          opened_to: "",
          review_reason: "",
          provider_key: "",
          include_unknown: false,
          status: "resolved_only",
        }}
        setCalibrationFilters={() => undefined}
        generateCalibrationExport={vi.fn(async () => undefined)}
        lastCalibrationManifest={{
          schema_version: 1,
          generated_at: "2026-04-12T08:00:00Z",
          snapshot_source: "live_rules",
          dataset_ready: true,
          tuning_ready: false,
          warnings: ["provider_support_below_target"],
          readiness: {
            overall_percent: 80,
            dataset_percent: 95,
            tuning_percent: 80,
            blockers: ["min_provider_support"],
            checks: [
              {
                key: "min_provider_support",
                scope: "tuning",
                current: 4,
                target: 5,
                ratio: 0.8,
                percent: 80,
                ready: false,
              },
            ],
          },
          filters: { status: "resolved_only" },
          row_counts: { raw_rows: 12, known_rows: 10, unknown_rows: 2 },
          coverage: { provider_profiles_count: 2, provider_key_coverage: 0.75, provider_pattern_candidates: 3 },
        }}
        lastCalibrationFilename="export.zip"
        previewError=""
        displayValue={(value) => String(value ?? "n/a")}
        formatExportWarning={(code) => code}
        formatReadinessCheckLabel={(key) => key}
        formatReadinessCheckValue={() => "4 / 5"}
      />
    );

    expect(screen.getByText("data.exports.readinessTitle")).toBeInTheDocument();
    expect(screen.getAllByText("80%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("min_provider_support").length).toBeGreaterThan(0);
  });
});
