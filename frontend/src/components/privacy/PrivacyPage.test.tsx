import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PrivacyPage, { CONTACT_URL } from "./PrivacyPage";

describe("PrivacyPage", () => {
  it("has one H1, then the sections with their anchors", () => {
    const { container } = render(<PrivacyPage />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Privacy policy");
    const ids = [...container.querySelectorAll("h2")].map((h) => h.id);
    expect(ids).toEqual(["browsing", "checking", "youtube", "cookies", "children", "your-choices"]);
  });

  it("links to the contact form as “contact us”, in a new tab", () => {
    render(<PrivacyPage />);
    const links = screen.getAllByRole("link", { name: /^contact us/ });
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) {
      expect(link).toHaveAttribute("href", CONTACT_URL);
      expect(link).toHaveAttribute("target", "_blank");
    }
  });

  it("states the retention times the backend keeps to", () => {
    render(<PrivacyPage />);
    expect(screen.getByText(/delete them after 14 days/)).toBeInTheDocument();
    expect(screen.getByText(/forgotten after an hour/)).toBeInTheDocument();
  });
});
