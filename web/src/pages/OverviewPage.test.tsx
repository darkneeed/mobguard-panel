import { cleanup, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { OverviewPage } from "./OverviewPage";
import { renderWithProviders } from "../test/renderWithProviders";

vi.mock("../api/client", () => ({
  api: {
    getOverview: vi.fn(),
    getModules: vi.fn(),
  }
}));

describe("OverviewPage", () => {
  const session = {
    telegram_id: 1,
    username: "owner",
    expires_at: "2026-04-11T00:00:00Z",
    permissions: ["overview.read", "data.read"]
  };

  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.useRealTimers();
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
      },
      pipeline: {
        queue_depth: 1,
        queued_count: 0,
        processing_count: 1,
        failed_count: 0,
        snapshot_updated_at: "2026-04-12T03:25:01Z",
        snapshot_age_seconds: 2,
        stale: false,
        enforcement_pending_count: 0,
        current_lag_seconds: 4,
        oldest_queued_age_seconds: 0,
        last_successful_drain_at: "2026-04-12T03:24:00Z",
        worker_status: "ok"
      },
      freshness: {
        overview_updated_at: "2026-04-12T03:25:00Z",
        overview_age_seconds: 3,
        pipeline_updated_at: "2026-04-12T03:25:01Z",
        pipeline_age_seconds: 2
      },
      module_config: {
        desired_revision: 7,
        total_count: 3,
        healthy_count: 2,
        stale_count: 1,
        up_to_date_count: 2,
        lagging_count: 1,
        up_to_date_healthy_count: 1,
        lagging_healthy_count: 1,
        stale_after_seconds: 180
      },
      realtime_usage: {
        active_users: 5,
        violating_users: 2,
        compliant_users: 3,
        active_window_seconds: 3600
      },
      enforcement: {
        active_total: 3,
        active_warning_count: 2,
        active_ban_count: 1,
        last_warning_at: "2026-04-12T03:20:00Z",
        last_ban_at: "2026-04-12T03:18:00Z",
        last_ban_duration_minutes: 60,
        last_event_type: "warning",
        last_event_at: "2026-04-12T03:20:00Z"
      }
    });
    vi.mocked(api.getModules).mockResolvedValue({
      items: [
        {
          module_id: "node-a",
          module_name: "Node A",
          status: "online",
          version: "1.0.0",
          protocol_version: "v1",
          config_revision_applied: 7,
          install_state: "online",
          managed: true,
          inbound_tags: ["TAG-A"],
          health_status: "ok",
          error_text: "",
          last_validation_at: "2026-04-12T03:25:00Z",
          spool_depth: 0,
          access_log_exists: true,
          last_seen_at: "2026-04-12T03:25:00Z",
          healthy: true,
          runtime_metrics: {
            activity_window_seconds: 3600,
            active_users: 5,
            recent_events: 7,
            system: {},
            processes: { match_count: 1, top: [] },
            collected_at: "2026-04-12T03:25:00Z",
          },
        },
      ],
      count: 1,
      summary: {
        activity_window_seconds: 3600,
        total_modules: 1,
        pending_modules: 0,
        healthy_modules: 1,
        warning_modules: 0,
        error_modules: 0,
        stale_modules: 0,
        modules_with_metrics: 1,
        active_users_total: 5,
        recent_events_total: 7,
        avg_cpu_percent: 12.5,
        peak_cpu_percent: 12.5,
        memory_total_bytes: 1024,
        memory_used_bytes: 512,
        disk_total_bytes: 2048,
        disk_used_bytes: 256,
        mobguard_process_cpu_percent: 1.5,
        mobguard_process_rss_bytes: 4096,
      },
    });

    renderWithProviders(<OverviewPage session={session} />, { route: "/overview" });

    expect(await screen.findByText("provider_conflict")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /alpha/i })).toBeInTheDocument();
    expect(screen.getByText("С ограничениями")).toBeInTheDocument();
    expect(screen.getAllByText("В норме").length).toBeGreaterThanOrEqual(1);
    expect(api.getOverview).toHaveBeenCalledTimes(1);
    expect(api.getModules).toHaveBeenCalledTimes(1);
  });

  it("keeps the last successful snapshot visible when polling fails", async () => {
    const intervalCallbacks: Array<{ callback: TimerHandler; delay?: number }> = [];
    vi.spyOn(window, "setInterval").mockImplementation(((callback: TimerHandler, delay?: number) => {
      intervalCallbacks.push({ callback, delay });
      return 1 as unknown as number;
    }) as typeof window.setInterval);
    vi.spyOn(window, "clearInterval").mockImplementation(() => {});
    vi.mocked(api.getOverview)
      .mockResolvedValueOnce({
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
        },
        pipeline: {
          queue_depth: 1,
          queued_count: 0,
          processing_count: 1,
          failed_count: 0,
          snapshot_updated_at: "2026-04-12T03:25:01Z",
          snapshot_age_seconds: 2,
          stale: false,
          enforcement_pending_count: 0,
          current_lag_seconds: 4,
          oldest_queued_age_seconds: 0,
          last_successful_drain_at: "2026-04-12T03:24:00Z",
          worker_status: "ok"
        },
        freshness: {
          overview_updated_at: "2026-04-12T03:25:00Z",
          overview_age_seconds: 3,
          pipeline_updated_at: "2026-04-12T03:25:01Z",
          pipeline_age_seconds: 2
        },
        module_config: {
          desired_revision: 7,
          total_count: 3,
          healthy_count: 2,
          stale_count: 1,
          up_to_date_count: 2,
          lagging_count: 1,
          up_to_date_healthy_count: 1,
          lagging_healthy_count: 1,
          stale_after_seconds: 180
        },
        realtime_usage: {
          active_users: 5,
          violating_users: 2,
          compliant_users: 3,
          active_window_seconds: 3600
        },
        enforcement: {
          active_total: 3,
          active_warning_count: 2,
          active_ban_count: 1,
          last_warning_at: "2026-04-12T03:20:00Z",
          last_ban_at: "2026-04-12T03:18:00Z",
          last_ban_duration_minutes: 60,
          last_event_type: "warning",
          last_event_at: "2026-04-12T03:20:00Z"
        }
      })
      .mockRejectedValueOnce(new Error("temporary refresh failure"));
    vi.mocked(api.getModules).mockResolvedValue({
      items: [],
      count: 0,
      summary: {
        activity_window_seconds: 3600,
        total_modules: 0,
        pending_modules: 0,
        healthy_modules: 0,
        warning_modules: 0,
        error_modules: 0,
        stale_modules: 0,
        modules_with_metrics: 0,
        active_users_total: 0,
        recent_events_total: 0,
        memory_total_bytes: 0,
        memory_used_bytes: 0,
        disk_total_bytes: 0,
        disk_used_bytes: 0,
        mobguard_process_cpu_percent: 0,
        mobguard_process_rss_bytes: 0,
      },
    });

    renderWithProviders(<OverviewPage session={session} />, { route: "/overview" });

    expect(await screen.findByText("provider_conflict")).toBeInTheDocument();

    const refreshInterval = intervalCallbacks.find((entry) => entry.delay === 10000);
    expect(refreshInterval).toBeTruthy();
    (refreshInterval?.callback as () => void)();

    expect(await screen.findByText(/temporary refresh failure/i)).toBeInTheDocument();
    expect(screen.getByText("provider_conflict")).toBeInTheDocument();
    expect(api.getOverview).toHaveBeenCalledTimes(2);
  });
});
