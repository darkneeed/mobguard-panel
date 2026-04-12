import { screen, waitFor } from "@testing-library/react";
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
  beforeEach(() => {
    vi.clearAllMocks();
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
        verdict: "UNSURE",
        confidence_band: "UNSURE",
        score: 42,
        isp: "ISP A",
        asn: 123,
        punitive_eligible: 1,
        severity: "critical",
        repeat_count: 2,
        reason_codes: ["provider_conflict"],
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
        verdict: "UNSURE",
        confidence_band: "UNSURE",
        score: 12,
        isp: "ISP B",
        asn: 456,
        punitive_eligible: 0,
        severity: "high",
        repeat_count: 1,
        reason_codes: ["unsure"],
        opened_at: "2026-04-11T00:00:00Z",
        updated_at: "2026-04-11T00:00:00Z",
        review_url: "https://example.test/reviews/2"
      }
    ],
    count: 2,
    page: 1,
    page_size: 24
  };

  it("resolves selected cases sequentially", async () => {
    vi.mocked(api.listReviews).mockResolvedValue(listPayload);
    vi.mocked(api.resolveReview).mockResolvedValue({});

    renderWithProviders(<ReviewQueuePage />, { route: "/queue" });

    await screen.findByText("alpha");
    await userEvent.click(screen.getByRole("button", { name: "Select page" }));
    await userEvent.click(screen.getByRole("button", { name: "Set selected to MOBILE" }));

    await waitFor(() => {
      expect(api.resolveReview).toHaveBeenNthCalledWith(1, "1", "MOBILE", "bulk action from queue (2)");
      expect(api.resolveReview).toHaveBeenNthCalledWith(2, "2", "MOBILE", "bulk action from queue (2)");
    });
  });

  it("allows changing cards per page and uses fixed review queue grid", async () => {
    vi.mocked(api.listReviews).mockResolvedValue(listPayload);

    renderWithProviders(<ReviewQueuePage />, { route: "/queue" });

    await screen.findByText("alpha");
    expect(api.listReviews).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 1,
        page_size: 24
      })
    );
    expect(document.querySelector(".review-queue-grid")).not.toBeNull();

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
});
