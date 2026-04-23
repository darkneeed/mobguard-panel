import { cleanup, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { DecisionsPage } from "./DecisionsPage";
import { renderWithProviders } from "../test/renderWithProviders";

vi.mock("../api/client", () => ({
  api: {
    getAutoDecisions: vi.fn(),
  },
}));

describe("DecisionsPage", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("loads and renders auto-decided events with enforcement state", async () => {
    vi.mocked(api.getAutoDecisions).mockResolvedValue({
      items: [
        {
          id: 1,
          created_at: "2026-04-24T10:00:00Z",
          ip: "1.2.3.4",
          target_ip: "1.2.3.4",
          target_scope_type: "ip_device",
          device_display: "Pixel 8",
          verdict: "HOME",
          confidence_band: "HIGH_HOME",
          score: 0.98,
          module_id: "node-a",
          module_name: "Node A",
          isp: "ISP A",
          inbound_tag: "TAG-A",
          decision_source: "rule_engine",
          enforcement_status: "applied",
          enforcement_job_type: "access_state",
          attempt_count: 1,
        },
      ],
      count: 1,
      page: 1,
      page_size: 50,
    });

    renderWithProviders(<DecisionsPage />, { route: "/decisions" });

    expect(await screen.findByText("1.2.3.4 · Pixel 8")).toBeInTheDocument();
    expect(screen.getByText("HOME / HIGH_HOME")).toBeInTheDocument();
    expect(screen.getByText(/Source Rule engine/)).toBeInTheDocument();
    expect(screen.getByText(/Enforcement Applied · Access squad · 1 attempts/)).toBeInTheDocument();
  });
});
