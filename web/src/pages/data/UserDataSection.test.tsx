import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { UserDataSection } from "./UserDataSection";

const t = (key: string) => key;

describe("UserDataSection", () => {
  it("renders search results and user card actions", () => {
    render(
      <MemoryRouter>
        <UserDataSection
          t={t}
          language="en"
          userQuery="alice"
          setUserQuery={() => undefined}
          userSearch={{
            items: [{ uuid: "uuid-1", username: "alice", system_id: 42, telegram_id: "1001" }],
            panel_match: null,
          }}
          userCard={{
            identity: { uuid: "uuid-1", username: "alice", system_id: 42, telegram_id: "1001" },
            flags: { active_ban: false, active_warning: true },
            review_cases: [{ id: 7, review_reason: "unsure", ip: "1.2.3.4", updated_at: "2026-04-12T03:25:00Z" }],
            analysis_events: [],
            history: [],
            usage_profile: {
              available: true,
              usage_profile_summary: "IPs 2; providers 2; devices 2",
              device_labels: ["iPhone 15", "Pixel 8"],
              os_families: ["iOS", "Android"],
              nodes: ["Node A", "Node B"],
              soft_reasons: ["geo_impossible_travel", "device_rotation"],
              geo_summary: { countries: ["RU", "DE"] },
              travel_flags: { geo_impossible_travel: true },
              top_ips: [{ ip: "1.2.3.4", count: 2 }],
              top_providers: [{ provider: "ISP A", count: 2 }],
              ongoing_duration_text: "2h",
            },
            panel_user: { status: "active" },
          }}
          userCardExport={null}
          banMinutes="15"
          setBanMinutes={() => undefined}
          trafficCapGigabytes="10"
          setTrafficCapGigabytes={() => undefined}
          strikeCount="1"
          setStrikeCount={() => undefined}
          warningCount="1"
          setWarningCount={() => undefined}
          searchUsers={vi.fn(async () => undefined)}
          loadUser={vi.fn(async () => undefined)}
          runUserAction={vi.fn(async () => undefined)}
          buildUserExport={vi.fn(async () => undefined)}
          downloadUserExport={vi.fn()}
          isPending={() => false}
          displayValue={(value) => String(value ?? "n/a")}
          formatPanelSquads={() => "FULL"}
          formatTrafficBytes={() => "1.00 GB"}
          renderProviderEvidence={() => null}
          activeUserAction=""
        />
      </MemoryRouter>
    );

    expect(screen.getByText("alice · data.users.systemLabel · data.users.telegramLabel")).toBeInTheDocument();
    expect(screen.getByText("data.users.cardTitle")).toBeInTheDocument();
    expect(screen.getByText("data.users.usageProfileTitle")).toBeInTheDocument();
    expect(screen.getByText("data.users.actionsTitle")).toBeInTheDocument();
  });
});
