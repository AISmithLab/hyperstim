import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CONTACT_URL } from "@/components/privacy/PrivacyPage";
import AboutPage, { ADVISORS, CONTRIBUTORS, LAB_URL } from "./AboutPage";

describe("AboutPage", () => {
  it("has one H1 and one H2, for getting in touch", () => {
    render(<AboutPage />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("About us");
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual(["Get in touch"]);
  });

  it("lists the contributors by last name, then the advisor", () => {
    render(<AboutPage />);
    const lastName = (name: string) => name.split(" ").at(-1)!;
    expect(CONTRIBUTORS.map(lastName)).toEqual([...CONTRIBUTORS.map(lastName)].sort());
    const terms = screen.getAllByRole("term").map((dt) => [dt.textContent, dt.nextElementSibling?.textContent]);
    expect(terms).toEqual([
      ["Contributors", CONTRIBUTORS.join(", ")],
      ["Advisor", ADVISORS.join(", ")],
    ]);
  });

  it.each([
    [/^AI Smith Lab/, LAB_URL],
    [/^contact form/, CONTACT_URL],
  ])("opens %s in a new tab", (name, href) => {
    render(<AboutPage />);
    const link = screen.getByRole("link", { name });
    expect(link).toHaveAttribute("href", href);
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("sets the site's name in bold italic in the text", () => {
    const { container } = render(<AboutPage />);
    const names = [...container.querySelectorAll("p span")].filter((el) => el.textContent === "HyperStim?");
    expect(names).toHaveLength(1);
    expect(names[0]).toHaveClass("font-bold", "italic");
  });
});
