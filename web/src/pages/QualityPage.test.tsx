import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { QualityPage } from "./QualityPage";
import { renderWithProviders } from "../test/renderWithProviders";

vi.mock("../api/client", () => ({
  api: {
    getQuality: vi.fn()
  }
}));

describe("QualityPage", () => {
  it("renders an error state when quality metrics fail", async () => {
    vi.mocked(api.getQuality).mockRejectedValue(new Error("quality down"));

    renderWithProviders(<QualityPage />);

    expect(await screen.findByText("quality down")).toBeInTheDocument();
  });
});
