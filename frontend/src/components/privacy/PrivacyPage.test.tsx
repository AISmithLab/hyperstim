import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OPEN_EVENT } from "@/lib/consent";
import PrivacyPage, { CONTACT_URL } from "./PrivacyPage";

describe("PrivacyPage", () => {
  it("has one H1, then the sections with their anchors", () => {
    const { container } = render(<PrivacyPage />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Privacy policy");
    const ids = [...container.querySelectorAll("h2")].map((h) => h.id);
    expect(ids).toEqual(["browsing", "checking", "cookies", "your-choices"]);
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

  it("states the log retention the backend keeps to", () => {
    render(<PrivacyPage />);
    expect(screen.getByText(/delete them after 14 days/)).toBeInTheDocument();
  });

  describe("changing the cookie choice", () => {
    afterEach(() => vi.unstubAllEnvs());

    it("reopens the banner from “cookie settings” in Your choices", async () => {
      vi.stubEnv("NEXT_PUBLIC_GA_ID", "G-TEST123");
      const opened = vi.fn();
      window.addEventListener(OPEN_EVENT, opened);
      render(<PrivacyPage />);
      await userEvent.setup().click(screen.getByRole("button", { name: "cookie settings" }));
      expect(opened).toHaveBeenCalled();
      window.removeEventListener(OPEN_EVENT, opened);
    });

    it("leaves the sentence out when there is no choice to make", () => {
      render(<PrivacyPage />);
      expect(screen.queryByText(/change your mind about cookies/)).toBeNull();
    });
  });
});
