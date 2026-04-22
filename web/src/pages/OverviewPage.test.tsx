import { cleanup, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { OverviewPage } from "./OverviewPage";
import { renderWithProviders } from "../test/renderWithProviders";

vi.mock("../api/client", () => ({
  api: {
    getOverview: vi.fn()
  }
}));

describe("OverviewPage", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("loads the aggregated overview snapshot with latest cases", async () => {
    vi.mocked(api.getOverview).mockResolvedValue({
      health: {
        status: "ok",
        admin_sessions: 2,
        ipinfo_token_present: true,
        db: { healthy: true, path: "/tmp/test.sqlite3" },
        core: {
          healthy: true,
          status: "embedded",
          mode: "embedded",
          updated_at: "2026-04-12T03:25:00Z"
        },
        live_rules: {
          revision: 7,
          updated_at: "2026-04-12T03:00:00Z",
          updated_by: "owner"
        },
        analysis_24h: {
          total: 4,
          score_zero_count: 1,
          score_zero_ratio: 0.25,
          asn_missing_count: 0,
          asn_missing_ratio: 0
        }
      },
      quality: {
        open_cases: 2,
        total_cases: 4,
        resolved_home: 1,
        resolved_mobile: 1,
        skipped: 0,
        active_learning_patterns: 2,
        active_sessions: 2,
        live_rules_revision: 7,
        live_rules_updated_at: "2026-04-12T03:00:00Z",
        live_rules_updated_by: "owner",
        top_noisy_asns: [{ asn_key: "AS12345", cnt: 2 }],
        mixed_providers: {
          open_cases: 1,
          conflict_cases: 1,
          conflict_rate: 1,
          top_open_cases: [
            {
              provider_key: "mts",
              open_cases: 1,
              conflict_cases: 1,
              home_cases: 1,
              mobile_cases: 0,
              unsure_cases: 0
            }
          ]
        },
        learning: {
          promoted: {
            active_patterns: 2
          }
        }
      },
      latest_cases: {
        items: [
          {
            id: 11,
            status: "OPEN",
            review_reason: "provider_conflict",
            module_id: "node-a",
            module_name: "Node A",
            uuid: "u-11",
            username: "alpha",
            system_id: 11,
            telegram_id: "111",
            ip: "1.1.1.1",
            tag: null,
            verdict: "UNSURE",
            confidence_band: "UNSURE",
            score: 12,
            isp: "ISP A",
            asn: 12345,
            punitive_eligible: 0,
            severity: "high",
            repeat_count: 2,
            reason_codes: ["provider_conflict"],
            opened_at: "2026-04-12T02:55:00Z",
            updated_at: "2026-04-12T03:25:00Z",
            review_url: "https://example.test/reviews/11"
          }
        ],
        count: 1,
        page: 1,
        page_size: 6
      }
    });

    renderWithProviders(<OverviewPage />, { route: "/overview" });

    expect(await screen.findByText("provider_conflict")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /alpha/i })).toBeInTheDocument();
    expect(api.getOverview).toHaveBeenCalledTimes(1);
  });
});
