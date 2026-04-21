import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { LearningCasesSection } from "./LearningCasesSection";

const t = (key: string) => key;

describe("LearningCasesSection", () => {
  it("renders cases mode as linked records", () => {
    render(
      <MemoryRouter>
        <LearningCasesSection
          mode="cases"
          t={t}
          language="en"
          learning={null}
          cases={{
            items: [
              {
                id: 7,
                status: "OPEN",
                review_reason: "unsure",
                module_id: "node-a",
                module_name: "Node A",
                uuid: "uuid-1",
                username: "alice",
                system_id: 42,
                telegram_id: "1001",
                ip: "1.2.3.4",
                tag: null,
                verdict: "UNSURE",
                confidence_band: "UNSURE",
                score: 0,
                isp: "ISP",
                asn: 123,
                punitive_eligible: 0,
                severity: "low",
                repeat_count: 1,
                reason_codes: ["unsure"],
                opened_at: "2026-04-12T03:20:00Z",
                updated_at: "2026-04-12T03:25:00Z",
                review_url: "https://example.test/reviews/7",
              },
            ],
            count: 1,
            page: 1,
            page_size: 25,
          }}
          setLearning={() => undefined}
          pushToast={vi.fn()}
        />
      </MemoryRouter>
    );

    expect(screen.getByText("#7 · alice")).toBeInTheDocument();
    expect(screen.getByText("unsure")).toBeInTheDocument();
  });
});
