import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { api } from "../api/client";
import { ToastProvider } from "../components/ToastProvider";
import { LanguageProvider } from "../localization";
import { ReviewDetailPage } from "./ReviewDetailPage";
import { renderWithProviders } from "../test/renderWithProviders";

vi.mock("../api/client", () => ({
  api: {
    getReview: vi.fn(),
    listReviews: vi.fn(),
    resolveReview: vi.fn()
  }
}));

describe("ReviewDetailPage", () => {
  const ownerSession = {
    telegram_id: 1,
    username: "owner",
    expires_at: "2026-04-11T00:00:00Z",
    permissions: ["reviews.read", "reviews.resolve"]
  };

  beforeEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it("renders evidence blocks in stacked readable cards", async () => {
    vi.mocked(api.getReview).mockResolvedValue({
      id: 34,
      username: "synthetic_user",
      ip: "128.71.75.0",
      latest_event: {
        bundle: {
          reasons: [
            {
              code: "provider_marker_missing",
              message: "Provider beeline matched without service markers",
              source: "provider_profile",
              direction: "NEUTRAL",
              weight: 0
            }
          ],
          signal_flags: {
            provider_evidence: {
              provider_key: "beelinemixed",
              provider_classification: "unknown",
              service_type_hint: "unknown",
              service_conflict: false,
              review_recommended: true,
              matched_aliases: ["vimpelcom", "vimpel"],
              provider_mobile_markers: [],
              provider_home_markers: []
            }
          },
          log: [
            "[ANALYSIS] Starting analysis for IP 128.71.75.0",
            "[ANALYSIS] Mixed ASN 16345 guarded by provider profile"
          ]
        }
      },
      related_cases: [
        {
          id: 21,
          username: "synthetic_user",
          ip: "128.70.186.177",
          verdict: "HOME",
          confidence_band: "HIGH_HOME",
          system_id: 258,
          telegram_id: "42424242",
          uuid: "84375f3b-048c-46bd-9133-52850be18241",
          updated_at: "2026-04-12T03:25:00Z"
        }
      ],
      ip_inventory: [
        {
          ip: "128.71.75.0",
          hit_count: 2,
          first_seen_at: "2026-04-12T01:25:00Z",
          last_seen_at: "2026-04-12T03:25:00Z",
          isp: "beelinemixed",
          asn: 16345
        },
        {
          ip: "128.70.186.177",
          hit_count: 1,
          first_seen_at: "2026-04-12T00:55:00Z",
          last_seen_at: "2026-04-12T00:55:00Z",
          isp: "beelinemixed",
          asn: 16345
        }
      ],
      module_inventory: [
        {
          module_id: "node-a",
          module_name: "Node A",
          first_seen_at: "2026-04-12T01:25:00Z",
          last_seen_at: "2026-04-12T03:25:00Z"
        },
        {
          module_id: "node-b",
          module_name: "Node B",
          first_seen_at: "2026-04-12T00:55:00Z",
          last_seen_at: "2026-04-12T00:55:00Z"
        }
      ],
      usage_profile: {
        available: true,
        usage_profile_summary: "IPs 2; providers 2; devices 2",
        device_labels: ["iPhone 15", "Pixel 8"],
        os_families: ["iOS", "Android"],
        nodes: ["Node A", "Node B"],
        soft_reasons: ["geo_impossible_travel", "device_rotation"],
        geo_summary: {
          countries: ["RU", "DE"],
          recent_locations: [{ country: "RU", city: "Moscow" }, { country: "DE", city: "Berlin" }]
        },
        travel_flags: {
          geo_country_jump: true,
          geo_impossible_travel: true,
          impossible_travel: [{ from_location: "RU, Moscow", to_location: "DE, Berlin" }]
        },
        top_ips: [{ ip: "128.71.75.0", count: 2 }],
        top_providers: [{ provider: "beelinemixed", count: 2 }],
        ongoing_duration_text: "2h",
        last_seen: "2026-04-12T03:25:00Z",
        updated_at: "2026-04-12T03:25:00Z"
      },
      resolutions: []
    });

    renderWithProviders(<ReviewDetailPage session={ownerSession} />, {
      route: "/reviews/34",
      path: "/reviews/:caseId"
    });

    const reasonTitle = await screen.findByText("provider_marker_missing");
    const reasonItem = reasonTitle.closest("li");

    expect(document.querySelector(".review-detail-grid")).not.toBeNull();
    expect(document.querySelector(".review-detail-log")).not.toBeNull();
    expect(reasonItem).toHaveClass("review-detail-item");
    expect(reasonItem?.querySelector(".review-detail-item-copy")?.textContent).toContain(
      "Provider beeline matched without service markers"
    );
    expect(screen.getByText("beelinemixed")).toBeInTheDocument();
    expect(screen.getByText("vimpelcom, vimpel")).toBeInTheDocument();
    expect(screen.getByText("Usage profile")).toBeInTheDocument();
    expect(screen.getByText("IPs 2; providers 2; devices 2")).toBeInTheDocument();
    expect(screen.getByText("Linked IP inventory")).toBeInTheDocument();
    expect(screen.getByText("Touched modules")).toBeInTheDocument();
    expect(screen.getByText("128.70.186.177")).toBeInTheDocument();
    expect(screen.getByText("Node B")).toBeInTheDocument();
  });

  it("opens the next case from the current queue after resolve", async () => {
    vi.mocked(api.getReview)
      .mockResolvedValueOnce({
        id: 34,
        username: "alpha",
        ip: "128.71.75.0",
        latest_event: { bundle: { reasons: [], signal_flags: {}, log: [] } },
        related_cases: [],
        resolutions: []
      })
      .mockResolvedValueOnce({
        id: 21,
        username: "beta",
        ip: "128.70.186.177",
        latest_event: { bundle: { reasons: [], signal_flags: {}, log: [] } },
        related_cases: [],
        resolutions: []
      });
    vi.mocked(api.resolveReview).mockResolvedValue({});
    vi.mocked(api.listReviews).mockResolvedValue({
      items: [
        {
          id: 21,
          status: "OPEN",
          review_reason: "unsure",
          module_id: "node-a",
          module_name: "Node A",
          uuid: "u-21",
          username: "beta",
          system_id: 21,
          telegram_id: "221",
          ip: "128.70.186.177",
          tag: null,
          verdict: "UNSURE",
          confidence_band: "UNSURE",
          score: 10,
          isp: "ISP B",
          asn: 16345,
          punitive_eligible: 0,
          severity: "high",
          repeat_count: 1,
          reason_codes: ["unsure"],
          opened_at: "2026-04-12T03:20:00Z",
          updated_at: "2026-04-12T03:25:00Z",
          review_url: "https://example.test/reviews/21"
        },
        {
          id: 8,
          status: "OPEN",
          review_reason: "unsure",
          module_id: "node-b",
          module_name: "Node B",
          uuid: "u-8",
          username: "gamma",
          system_id: 8,
          telegram_id: "88",
          ip: "10.0.0.8",
          tag: null,
          verdict: "UNSURE",
          confidence_band: "UNSURE",
          score: 8,
          isp: "ISP C",
          asn: 123,
          punitive_eligible: 0,
          severity: "medium",
          repeat_count: 1,
          reason_codes: ["unsure"],
          opened_at: "2026-04-12T03:10:00Z",
          updated_at: "2026-04-12T03:15:00Z",
          review_url: "https://example.test/reviews/8"
        }
      ],
      count: 2,
      page: 1,
      page_size: 24
    });

    render(
      <MemoryRouter
        initialEntries={[
          {
            pathname: "/reviews/34",
            state: {
              reviewQueueSearch: "status=OPEN&page=1&page_size=24&sort=updated_desc",
              reviewQueueItemIds: [34, 21, 8],
              reviewQueueCurrentIndex: 0
            }
          }
        ]}
      >
        <LanguageProvider language="en" setLanguage={() => undefined}>
          <ToastProvider>
            <Routes>
              <Route path="/reviews/:caseId" element={<ReviewDetailPage session={ownerSession} />} />
            </Routes>
          </ToastProvider>
        </LanguageProvider>
      </MemoryRouter>
    );

    await screen.findByRole("heading", { name: "Review case #34" });
    await userEvent.click(screen.getByRole("button", { name: "Mark MOBILE" }));

    expect(api.resolveReview).toHaveBeenCalledWith("34", "MOBILE", "");
    expect(api.listReviews).toHaveBeenCalledWith({
      status: "OPEN",
      page: "1",
      page_size: "24",
      sort: "updated_desc"
    });
    expect(await screen.findByRole("heading", { name: "Review case #21" })).toBeInTheDocument();
  });
});
