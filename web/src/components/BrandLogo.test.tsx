import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BrandLogo } from "./BrandLogo";

describe("BrandLogo", () => {
  it("falls back to built-in logo when custom image fails", () => {
    render(<BrandLogo logoUrl="https://cdn.example.com/logo.png" alt="Acme Shield" />);

    const image = screen.getByAltText("Acme Shield");
    expect(image).toHaveAttribute("src", "https://cdn.example.com/logo.png");

    fireEvent.error(image);

    expect(image).toHaveAttribute("src", "/mobguard-cat.png");
  });
});
