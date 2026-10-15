import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Footer from "./Footer";

describe("Footer", () => {
  it("links FAQ to the common questions on How it works", () => {
    render(<Footer />);
    expect(screen.getByRole("link", { name: "FAQ" })).toHaveAttribute("href", "/how-it-works#questions");
  });
});
