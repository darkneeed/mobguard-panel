import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api, ReviewListResponse } from "../api/client";
import { ReviewQueuePage } from "./ReviewQueuePage";
import { renderWithProviders } from "../test/renderWithProviders";

vi.mock("../api/client", () => ({
  api: {
    listReviews: vi.fn(),
    resolveReview: vi.fn()
  }
}));

describe("ReviewQueuePage", () => {
  const ownerSession = {
    telegram_id: 1,
    username: "owner",
    expires_at: "2026-04-11T00:00:00Z",
    permissions: ["reviews.read", "reviews.resolve", "reviews.recheck", "data.read"]
  };

  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  const listPayload: ReviewListResponse = {
    items: [
      {
        id: 1,
        status: "OPEN",
        review_reason: "provider_conflict",
        module_id: "node-a",
        module_name: "Node A",
        uuid: "u-1",
        username: "alpha",
        system_id: 10,
        telegram_id: "11",
        ip: "1.1.1.1",
        tag: null,
        target_scope_type: "ip_device",
        device_display: "Pixel 8",
        verdict: "UNSURE",
        confidence_band: "UNSURE",
        score: 42,
        isp: "ISP A",
        asn: 123,
        hard_flags: ["sharing_hwid_limit_exceeded"],
        punitive_eligible: 1,
        severity: "critical",
        repeat_count: 2,
        reason_codes: ["provider_conflict", "provider_marker_missing", "behavior_churn"],
        ip_inventory: [
          {
            ip: "1.1.1.1",
            hit_count: 2,
            first_seen_at: "2026-04-10T23:00:00Z",
            last_seen_at: "2026-04-11T00:00:00Z",
            isp: "ISP A",
            asn: 123
          },
          {
            ip: "1.1.1.2",
            hit_count: 1,
            first_seen_at: "2026-04-10T22:00:00Z",
            last_seen_at: "2026-04-10T22:00:00Z",
            isp: "ISP A",
            asn: 123
          }
        ],
        distinct_ip_count: 2,
        module_inventory: [
          {
            module_id: "node-a",
            module_name: "Node A",
            first_seen_at: "2026-04-10T23:00:00Z",
            last_seen_at: "2026-04-11T00:00:00Z"
          },
          {
            module_id: "node-c",
            module_name: "Node C",
            first_seen_at: "2026-04-10T22:00:00Z",
            last_seen_at: "2026-04-10T22:00:00Z"
          }
        ],
        module_count: 2,
        provider_key: "mts",
        provider_classification: "mixed",
        provider_service_hint: "home",
        provider_conflict: true,
        provider_review_recommended: true,
        usage_profile_summary: "IPs 3; devices 2; flags geo_impossible_travel",
        usage_profile_signal_count: 2,
        usage_profile_priority: 980,
        usage_profile_soft_reasons: ["geo_impossible_travel", "device_rotation"],
        usage_profile_ongoing_duration_text: "2h",
        opened_at: "2026-04-11T00:00:00Z",
        updated_at: "2026-04-11T00:00:00Z",
        review_url: "https://example.test/reviews/1"
      },
      {
        id: 2,
        status: "OPEN",
        review_reason: "unsure",
        module_id: "node-b",
        module_name: "Node B",
        uuid: "u-2",
        username: "beta",
        system_id: 20,
        telegram_id: "22",
        ip: "2.2.2.2",
        tag: null,
        target_scope_type: "subject_ip",
        shared_account_suspected: true,
        verdict: "UNSURE",
        confidence_band: "UNSURE",
        score: 12,
        isp: "ISP B",
        asn: 456,
        hard_flags: ["mobile_config_on_home_network"],
        punitive_eligible: 0,
        severity: "high",
        repeat_count: 1,
        reason_codes: ["unsure"],
        ip_inventory: [
          {
            ip: "2.2.2.2",
            hit_count: 1,
            first_seen_at: "2026-04-11T00:00:00Z",
            last_seen_at: "2026-04-11T00:00:00Z",
            isp: "ISP B",
            asn: 456
          }
        ],
        distinct_ip_count: 1,
        module_inventory: [
          {
            module_id: "node-b",
            module_name: "Node B",
            first_seen_at: "2026-04-11T00:00:00Z",
            last_seen_at: "2026-04-11T00:00:00Z"
          }
        ],
        module_count: 1,
        provider_key: "t2",
        provider_classification: "mobile",
        provider_service_hint: "mobile",
        provider_conflict: false,
        provider_review_recommended: false,
        usage_profile_summary: "",
        usage_profile_signal_count: 0,
        usage_profile_priority: 210,
        usage_profile_soft_reasons: [],
        usage_profile_ongoing_duration_text: "",
        opened_at: "2026-04-11T00:00:00Z",
        updated_at: "2026-04-11T00:00:00Z",
        review_url: "https://example.test/reviews/2"
      },
      {
        id: 3,
        status: "OPEN",
        review_reason: "unsure",
        module_id: "node-c",
        module_name: "Node C",
        uuid: "u-3",
        username: null,
        system_id: 30,
        telegram_id: null,
        ip: "3.3.3.3",
        tag: null,
        target_scope_type: "ip_only",
        verdict: "UNSURE",
        confidence_band: "UNSURE",
        score: 9,
        isp: "ISP C",
        asn: null,
        hard_flags: ["manual_rule_applied"],
        punitive_eligible: 0,
        severity: "low",
        repeat_count: 1,
        reason_codes: ["mixed_asn", "mixed_asn_guarded"],
        ip_inventory: [
          {
            ip: "3.3.3.3",
            hit_count: 1,
            first_seen_at: "2026-04-11T00:00:00Z",
            last_seen_at: "2026-04-11T00:00:00Z",
            isp: "ISP C",
            asn: null
          }
        ],
        distinct_ip_count: 1,
        module_inventory: [
          {
            module_id: "node-c",
            module_name: "Node C",
            first_seen_at: "2026-04-11T00:00:00Z",
            last_seen_at: "2026-04-11T00:00:00Z"
          }
        ],
        module_count: 1,
        provider_key: "mixed-c",
        provider_classification: "mixed",
        provider_service_hint: "unknown",
        provider_conflict: false,
        provider_review_recommended: true,
        usage_profile_summary: "",
        usage_profile_signal_count: 0,
        usage_profile_priority: 240,
        usage_profile_soft_reasons: [],
        usage_profile_ongoing_duration_text: "",
        opened_at: "2026-04-11T00:00:00Z",
        updated_at: "2026-04-11T00:00:00Z",
        review_url: "https://example.test/reviews/3"
      }
    ],
    count: 3,
    page: 1,
    page_size: 24
  };

  it("resolves selected cases sequentially", async () => {
    vi.mocked(api.listReviews).mockResolvedValue(listPayload);
    vi.mocked(api.resolveReview).mockResolvedValue({});

    renderWithProviders(<ReviewQueuePage session={ownerSession} />, { route: "/queue" });

    expect((await screen.findAllByText("alpha")).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: "Select page" }));
    await userEvent.click(screen.getByRole("button", { name: "Mark as mobile" }));

    await waitFor(() => {
      expect(api.resolveReview).toHaveBeenNthCalledWith(1, "1", "MOBILE", "bulk action from queue (3)");
      expect(api.resolveReview).toHaveBeenNthCalledWith(2, "2", "MOBILE", "bulk action from queue (3)");
      expect(api.resolveReview).toHaveBeenNthCalledWith(3, "3", "MOBILE", "bulk action from queue (3)");
    });
  });

  it("allows changing cards per page and uses fixed review queue grid", async () => {
    vi.mocked(api.listReviews).mockResolvedValue(listPayload);

    renderWithProviders(<ReviewQueuePage session={ownerSession} />, { route: "/queue" });

    await screen.findByText("alpha");
    expect(api.listReviews).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 1,
        page_size: 24,
        sort: "priority_desc"
      })
    );
    expect(document.querySelector(".review-queue-grid")).not.toBeNull();
    expect(screen.getByText("By device")).toBeInTheDocument();
    expect(screen.getByText("By account")).toBeInTheDocument();
    expect(screen.getByText("IP only")).toBeInTheDocument();
    expect(screen.getByText("2 IPs on this device")).toBeInTheDocument();
    expect(screen.getByText("1 IPs on this account")).toBeInTheDocument();
    expect(screen.getByText("1 IPs in this IP-only context")).toBeInTheDocument();
    expect(screen.getByText("1.1.1.1 ×2 · 1h")).toBeInTheDocument();
    expect(screen.getByText("3.3.3.3 ×1 · 0m")).toBeInTheDocument();
    expect(screen.getByText("ISP A")).toBeInTheDocument();
    expect(screen.getByText("HWID limit exceeded")).toBeInTheDocument();
    expect(screen.getByText("Mobile config on HOME")).toBeInTheDocument();
    expect(screen.getByText("Manual rule")).toBeInTheDocument();
    expect(screen.queryByText("Provider conflict")).not.toBeInTheDocument();
    expect(screen.queryByText("Нет маркера типа сети")).not.toBeInTheDocument();
    expect(screen.queryByText("Резкое путешествие")).not.toBeInTheDocument();
    expect(screen.queryByText("Ротация IP")).not.toBeInTheDocument();
    expect(screen.queryByText("ASN смешанного типа")).not.toBeInTheDocument();
    expect(screen.queryByText("Manual review")).not.toBeInTheDocument();
    expect(screen.queryByText("priority 980")).not.toBeInTheDocument();
    expect(screen.queryByText(/^OPEN$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Inbound:/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Console" })).toHaveAttribute("href", "/data/console");

    const [pageSizeSelect] = screen.getAllByLabelText("Cards per page");
    await userEvent.selectOptions(pageSizeSelect, "48");

    await waitFor(() => {
      expect(api.listReviews).toHaveBeenLastCalledWith(
        expect.objectContaining({
          page: 1,
          page_size: 48
        })
      );
    });
  });

  it("saves and reapplies queue filters from localStorage", async () => {
    vi.mocked(api.listReviews).mockResolvedValue(listPayload);

    renderWithProviders(<ReviewQueuePage session={ownerSession} />, { route: "/queue" });

    await screen.findByText("alpha");
    await userEvent.click(screen.getByRole("button", { name: "Filters" }));
    await userEvent.type(screen.getByPlaceholderText("Username"), "alice");
    await userEvent.click(screen.getByRole("button", { name: "Save current" }));

    expect(window.localStorage.getItem("mobguard.reviewQueue.savedFilters")).toContain("\"username\":\"alice\"");

    await userEvent.click(screen.getByRole("button", { name: "Reset filters" }));
    await userEvent.click(screen.getByRole("button", { name: "Apply saved" }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Username")).toHaveValue("alice");
    });
  });
});
