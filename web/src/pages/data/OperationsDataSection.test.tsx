import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OperationsDataSection } from "./OperationsDataSection";

const t = (key: string) => key;

describe("OperationsDataSection", () => {
  it("renders override admin controls in overrides mode", () => {
    render(
      <OperationsDataSection
        mode="overrides"
        t={t}
        language="en"
        violations={null}
        overrides={{
          exact_ip: [{ ip: "1.2.3.4", decision: "HOME", expires_at: "2026-04-12T03:25:00Z" }],
          unsure_patterns: [{ ip_pattern: "1.2.3.*", decision: "MOBILE", timestamp: "2026-04-12T03:25:00Z" }],
        }}
        cache={null}
        exactOverrideIp=""
        setExactOverrideIp={() => undefined}
        exactOverrideDecision="HOME"
        setExactOverrideDecision={() => undefined}
        unsureOverrideIp=""
        setUnsureOverrideIp={() => undefined}
        unsureOverrideDecision="HOME"
        setUnsureOverrideDecision={() => undefined}
        selectedCacheIp=""
        setSelectedCacheIp={() => undefined}
        cacheDraft={{}}
        setCacheDraft={() => undefined}
        saveExactOverride={vi.fn(async () => undefined)}
        saveUnsureOverride={vi.fn(async () => undefined)}
        saveCachePatch={vi.fn(async () => undefined)}
        setOverrides={() => undefined}
        setCache={() => undefined}
        pushToast={vi.fn()}
        withPending={async (_key, action) => action()}
        isPending={() => false}
        displayValue={(value) => String(value ?? "n/a")}
        formatDecisionLabel={(value) => String(value)}
      />
    );

    expect(screen.getByText("data.overrides.exactTitle")).toBeInTheDocument();
    expect(screen.getByText("data.overrides.unsureTitle")).toBeInTheDocument();
    expect(screen.getAllByText("data.overrides.delete").length).toBe(2);
  });
});
