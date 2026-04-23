import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { renderWithProviders } from "../test/renderWithProviders";
import { ModulesPage } from "./ModulesPage";

vi.mock("../api/client", () => ({
  api: {
    getModules: vi.fn(),
    getModuleDetail: vi.fn(),
    createModule: vi.fn(),
    updateModule: vi.fn(),
    revealModuleToken: vi.fn()
  }
}));

describe("ModulesPage", () => {
  const ownerSession = {
    telegram_id: 1,
    username: "owner",
    expires_at: "2026-04-11T00:00:00Z",
    permissions: ["modules.read", "modules.write", "modules.token_reveal"]
  };

  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.useRealTimers();
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined)
      }
    });
  });

  it("creates a module and shows install bundle with revealed token", async () => {
    vi.mocked(api.getModules).mockResolvedValue({
      items: [],
      count: 0,
      pipeline: {
        queue_depth: 0,
        queued_count: 0,
        processing_count: 0,
        failed_count: 0,
        snapshot_updated_at: "2026-04-12T00:00:00Z",
        snapshot_age_seconds: 1,
        stale: false,
        enforcement_pending_count: 0,
        worker_status: "ok"
      }
    });
    vi.mocked(api.createModule).mockResolvedValue({
      module: {
        module_id: "module-abc123",
        module_name: "Node Alpha",
        status: "pending_install",
        version: "",
        protocol_version: "v1",
        config_revision_applied: 0,
        install_state: "pending_install",
        managed: true,
        inbound_tags: ["DEFAULT-INBOUND"],
        health_status: "warn",
        error_text: "",
        last_validation_at: "2026-04-12T00:00:00",
        spool_depth: 0,
        access_log_exists: false,
        token_reveal_available: true,
        first_seen_at: "2026-04-12T00:00:00",
        last_seen_at: "",
        healthy: false,
        open_review_cases: 0,
        analysis_events_count: 0
      },
      install: {
        compose_yaml: "MODULE_TOKEN=__PASTE_TOKEN__",
        module_token: "panel-generated-token"
      }
    });

    renderWithProviders(<ModulesPage session={ownerSession} />);

    await userEvent.click(await screen.findByRole("button", { name: "Create module" }));

    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Display name"), "Node Alpha");
    await userEvent.type(within(dialog).getByLabelText("INBOUND tags"), "DEFAULT-INBOUND");
    await userEvent.click(within(dialog).getByRole("button", { name: "Create module" }));

    await waitFor(() => {
      expect(api.createModule).toHaveBeenCalledWith({
        module_name: "Node Alpha",
        inbound_tags: ["DEFAULT-INBOUND"]
      });
    });

    expect(await screen.findByText("panel-generated-token")).toBeInTheDocument();
    expect(screen.getByText("MODULE_TOKEN=__PASTE_TOKEN__")).toBeInTheDocument();
  });

  it("reveals token for an existing managed module", async () => {
    vi.mocked(api.getModules).mockResolvedValue({
      items: [
        {
          module_id: "module-abc123",
          module_name: "Node Alpha",
          status: "online",
          version: "1.0.0",
          protocol_version: "v1",
          config_revision_applied: 3,
          install_state: "online",
          managed: true,
          inbound_tags: ["DEFAULT-INBOUND"],
          health_status: "error",
          error_text: "Access log path not found",
          last_validation_at: "2026-04-12T00:02:00",
          spool_depth: 4,
          access_log_exists: false,
          first_seen_at: "2026-04-12T00:00:00",
          last_seen_at: "2026-04-12T00:01:00",
          healthy: true,
          open_review_cases: 0,
          analysis_events_count: 1
        }
      ],
      count: 1,
      pipeline: {
        queue_depth: 4,
        queued_count: 2,
        processing_count: 2,
        failed_count: 0,
        snapshot_updated_at: "2026-04-12T00:01:00Z",
        snapshot_age_seconds: 1,
        stale: false,
        enforcement_pending_count: 0,
        worker_status: "ok"
      }
    });
    vi.mocked(api.getModuleDetail).mockResolvedValue({
      module: {
        module_id: "module-abc123",
        module_name: "Node Alpha",
        status: "online",
        version: "1.0.0",
        protocol_version: "v1",
        config_revision_applied: 3,
        install_state: "online",
        managed: true,
        inbound_tags: ["DEFAULT-INBOUND"],
        health_status: "error",
        error_text: "Access log path not found",
        last_validation_at: "2026-04-12T00:02:00",
        spool_depth: 4,
        access_log_exists: false,
        token_reveal_available: true,
        first_seen_at: "2026-04-12T00:00:00",
        last_seen_at: "2026-04-12T00:01:00",
        healthy: true,
        open_review_cases: 0,
        analysis_events_count: 1
      },
      install: {
        compose_yaml: "MODULE_TOKEN=__PASTE_TOKEN__"
      }
    });
    vi.mocked(api.revealModuleToken).mockResolvedValue({
      module_id: "module-abc123",
      module_token: "revealed-token"
    });

    renderWithProviders(<ModulesPage session={ownerSession} />);

    await screen.findByText("Node Alpha");
    expect(api.getModuleDetail).not.toHaveBeenCalled();

    await userEvent.click(screen.getAllByRole("button", { name: "Open details" })[0]);

    await waitFor(() => {
      expect(api.getModuleDetail).toHaveBeenCalledWith("module-abc123");
    });

    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Reveal token" }));

    await waitFor(() => {
      expect(api.revealModuleToken).toHaveBeenCalledWith("module-abc123");
    });
    expect(await screen.findByText("revealed-token")).toBeInTheDocument();
    expect(screen.getAllByText("Access log path not found")).toHaveLength(2);
  });

  it("polls modules and labels stale pipeline snapshots", async () => {
    const intervalCallbacks: Array<{ callback: TimerHandler; delay?: number }> = [];
    vi.spyOn(window, "setInterval").mockImplementation(((callback: TimerHandler, delay?: number) => {
      intervalCallbacks.push({ callback, delay });
      return 1 as unknown as number;
    }) as typeof window.setInterval);
    vi.spyOn(window, "clearInterval").mockImplementation(() => {});
    vi.mocked(api.getModules)
      .mockResolvedValueOnce({
        items: [
          {
            module_id: "module-abc123",
            module_name: "Node Alpha",
            status: "online",
            version: "1.0.0",
            protocol_version: "v1",
            config_revision_applied: 3,
            install_state: "online",
            managed: true,
            inbound_tags: ["DEFAULT-INBOUND"],
            health_status: "ok",
            error_text: "",
            last_validation_at: "2026-04-12T00:02:00",
            spool_depth: 4,
            access_log_exists: true,
            first_seen_at: "2026-04-12T00:00:00",
            last_seen_at: "2026-04-12T00:01:00",
            healthy: true,
            open_review_cases: 0,
            analysis_events_count: 1
          }
        ],
        count: 1,
        pipeline: {
          queue_depth: 902673,
          queued_count: 902600,
          processing_count: 73,
          failed_count: 2,
          snapshot_updated_at: "2026-04-12T00:01:00Z",
          snapshot_age_seconds: 12,
          stale: true,
          enforcement_pending_count: 1,
          worker_status: "ok"
        }
      })
      .mockResolvedValueOnce({
        items: [
          {
            module_id: "module-abc123",
            module_name: "Node Alpha",
            status: "online",
            version: "1.0.0",
            protocol_version: "v1",
            config_revision_applied: 3,
            install_state: "online",
            managed: true,
            inbound_tags: ["DEFAULT-INBOUND"],
            health_status: "ok",
            error_text: "",
            last_validation_at: "2026-04-12T00:02:00",
            spool_depth: 4,
            access_log_exists: true,
            first_seen_at: "2026-04-12T00:00:00",
            last_seen_at: "2026-04-12T00:01:00",
            healthy: true,
            open_review_cases: 0,
            analysis_events_count: 1
          }
        ],
        count: 1,
        pipeline: {
          queue_depth: 18,
          queued_count: 10,
          processing_count: 8,
          failed_count: 0,
          snapshot_updated_at: "2026-04-12T00:01:15Z",
          snapshot_age_seconds: 1,
          stale: false,
          enforcement_pending_count: 0,
          worker_status: "ok"
        }
      });

    renderWithProviders(<ModulesPage session={ownerSession} />);

    expect((await screen.findAllByText("902673 · stale snapshot")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Snapshot age 12s").length).toBeGreaterThan(0);

    const refreshInterval = intervalCallbacks.find((entry) => entry.delay === 15000);
    expect(refreshInterval).toBeTruthy();
    (refreshInterval?.callback as () => void)();

    await waitFor(() => {
      expect(api.getModules).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(screen.queryAllByText("902673 · stale snapshot")).toHaveLength(0);
    });
    expect(screen.getAllByText("Snapshot age 1s").length).toBeGreaterThan(0);
  });
});
