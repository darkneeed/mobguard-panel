import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { renderWithProviders } from "../test/renderWithProviders";
import { DataPage } from "./DataPage";

vi.mock("../api/client", () => ({
  api: {
    getConsoleEntries: vi.fn(),
    getAnalysisEvents: vi.fn(),
    previewCalibration: vi.fn(),
    exportCalibration: vi.fn()
  }
}));

describe("DataPage console", () => {
  it("loads unified console entries with system and module sources", async () => {
    vi.mocked(api.getConsoleEntries).mockResolvedValue({
      items: [
        {
          id: "system:1",
          timestamp: "2026-04-12T08:00:00Z",
          source: "system",
          level: "warn",
          message: "Pipeline snapshot refresh skipped because SQLite is busy",
          service_name: "mobguard-api",
          logger_name: "api.services.ingest_pipeline",
          meta: { lineno: 720 }
        },
        {
          id: "module_event:2",
          timestamp: "2026-04-12T08:00:01Z",
          source: "module_event",
          level: "info",
          message: "Node A accepted event evt-1 from 1.2.3.4 tag TAG-A [queued]",
          module_id: "node-a",
          module_name: "Node A",
          event_uid: "evt-1",
          payload: { ip: "1.2.3.4", tag: "TAG-A" },
          meta: { processing_state: "queued" }
        }
      ],
      count: 2,
      page: 1,
      page_size: 100,
      source_counts: {
        system: 1,
        module_event: 1,
        module_heartbeat: 0
      }
    });

    renderWithProviders(<DataPage />, {
      route: "/data/console",
      path: "/data/:section"
    });

    await waitFor(() => {
      expect(api.getConsoleEntries).toHaveBeenCalledWith({
        q: "",
        source: "",
        level: "",
        module_id: "",
        page: 1,
        page_size: 50
      });
    });

    expect(await screen.findByText("Pipeline snapshot refresh skipped because SQLite is busy")).toBeInTheDocument();
    expect(screen.getByText("Node A accepted event evt-1 from 1.2.3.4 tag TAG-A [queued]")).toBeInTheDocument();
  });
});
