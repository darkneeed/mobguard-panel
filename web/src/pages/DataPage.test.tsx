import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { renderWithProviders } from "../test/renderWithProviders";
import { DataPage } from "./DataPage";

vi.mock("../api/client", () => ({
  api: {
    getAnalysisEvents: vi.fn(),
    previewCalibration: vi.fn(),
    exportCalibration: vi.fn()
  }
}));

describe("DataPage exports", () => {
  it("loads calibration readiness preview automatically for exports tab", async () => {
    vi.mocked(api.previewCalibration).mockResolvedValue({
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
            key: "provider_profiles_present",
            scope: "dataset",
            current: 1,
            target: 1,
            ratio: 1,
            percent: 100,
            ready: true
          },
          {
            key: "min_provider_support",
            scope: "tuning",
            current: 4,
            target: 5,
            ratio: 0.8,
            percent: 80,
            ready: false
          }
        ]
      },
      filters: {
        status: "resolved_only",
        include_unknown: false
      },
      row_counts: {
        raw_rows: 12,
        known_rows: 10,
        unknown_rows: 2
      },
      coverage: {
        provider_profiles_count: 2,
        provider_key_coverage: 0.75,
        provider_pattern_candidates: 3
      }
    });

    renderWithProviders(<DataPage />, {
      route: "/data/exports",
      path: "/data/:section"
    });

    await waitFor(() => {
      expect(api.previewCalibration).toHaveBeenCalledWith({
        opened_from: "",
        opened_to: "",
        review_reason: "",
        provider_key: "",
        include_unknown: false,
        status: "resolved_only"
      });
    });

    expect(await screen.findByText("Overall readiness")).toBeInTheDocument();
    expect(screen.getAllByText("80%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Minimum provider support").length).toBeGreaterThan(0);
  });
});

describe("DataPage events", () => {
  it("loads normalized analysis events and exposes review links", async () => {
    vi.mocked(api.getAnalysisEvents).mockResolvedValue({
      items: [
        {
          id: 11,
          created_at: "2026-04-12T08:00:00Z",
          ip: "1.2.3.4",
          target_ip: "1.2.3.4",
          target_scope_type: "ip_device",
          inbound_tag: "TAG-A",
          module_name: "Node A",
          isp: "ISP A",
          asn: 12345,
          device_display: "Pixel 8",
          review_case_id: 77
        }
      ],
      count: 1,
      page: 1,
      page_size: 50
    });

    renderWithProviders(<DataPage />, {
      route: "/data/events",
      path: "/data/:section"
    });

    await waitFor(() => {
      expect(api.getAnalysisEvents).toHaveBeenCalledWith({
        q: "",
        ip: "",
        device_id: "",
        module_id: "",
        tag: "",
        provider: "",
        asn: "",
        verdict: "",
        confidence_band: "",
        has_review_case: "",
        page: 1,
        page_size: 50,
        sort: "created_desc"
      });
    });

    expect(await screen.findByText("1.2.3.4 · Pixel 8")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Case: #77" })).toHaveAttribute("href", "/reviews/77");
  });
});
