import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getMeta, getVideos, type Meta } from "@/lib/api";
import { expectNoAxeViolations } from "@/test/axe";
import Hero from "./Hero";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getMeta: vi.fn(),
  getVideos: vi.fn(),
}));

const meta = (changes: Partial<Meta> = {}): Meta => ({
  videoCount: 16402,
  channelCount: 542,
  updatedAt: "2026-10-26",
  addedLast7Days: 1043,
  channelCount7DaysAgo: 540,
  lastAddedAt: "2026-10-26T10:00:00Z",
  referenceCount: 16375,
  channelsCheckedAt: null,
  ...changes,
});

/** What a screen reader reads: the text without the moving digits (aria-hidden). */
function readable(element: Element | null): string {
  const copy = element!.cloneNode(true) as Element;
  copy.querySelectorAll("[aria-hidden='true']").forEach((hidden) => hidden.remove());
  return copy.textContent!.replace(/\s+/g, " ").trim();
}

const pastWeek = (total: number) =>
  vi.mocked(getVideos).mockResolvedValue({ items: [], total, asOf: "2026-10-26T10:00:00Z" });

beforeEach(() => {
  pastWeek(1043);
  // Reduced motion: the numbers show at once.
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("reduced-motion"), media: query }));
});

describe("Hero", () => {
  it("says how many videos and channels, and how many were added in the past week", async () => {
    vi.mocked(getMeta).mockResolvedValue(meta());
    render(<Hero />);
    const pill = await screen.findByRole("link", { name: /in the past week/ });
    expect(readable(pill)).toBe("+1,043 videos in the past week");
    expect(pill).toHaveClass("bg-sky", "text-navy", "rounded-full");
    // It opens the rankings with the videos it counts.
    expect(pill).toHaveAttribute("href", expect.stringMatching(/^\/rankings\?q=added%3A%3E\d{4}-\d{2}-\d{2}$/));
    expect(readable(screen.getByText(/channels to better/))).toBe(
      "Explore and compare 16,402 videos from 542 channels to better understand what your child is watching.",
    );
  });

  it("leaves the pill out when nothing was added in the past week", async () => {
    vi.mocked(getMeta).mockResolvedValue(meta());
    pastWeek(0);
    render(<Hero />);
    expect(readable(await screen.findByText(/channels to better/))).toContain("16,402 videos from 542 channels");
    expect(screen.queryByText(/in the past week/)).not.toBeInTheDocument();
  });

  it("shows the sentence and the pill at once, with room kept for the numbers", () => {
    vi.mocked(getMeta).mockReturnValue(new Promise(() => {}));
    render(<Hero />);
    expect(screen.getByText(/channels to better/)).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText(/in the past week/)).toBeInTheDocument();
    expect(screen.queryByTestId("rolling-number")).not.toBeInTheDocument();
  });

  it("says “thousands of” if the numbers can't be had", async () => {
    vi.mocked(getMeta).mockRejectedValue(new Error("offline"));
    render(<Hero />);
    expect(await screen.findByText(/Explore and compare thousands of videos/)).toBeInTheDocument();
    expect(screen.queryByText(/in the past week/)).not.toBeInTheDocument();
  });

  it("has no accessibility violations, loading and loaded", async () => {
    let resolve!: (m: Meta) => void;
    vi.mocked(getMeta).mockReturnValue(new Promise((r) => (resolve = r)));
    render(<Hero />);
    await expectNoAxeViolations();
    resolve(meta());
    await screen.findByRole("link", { name: /in the past week/ });
    await expectNoAxeViolations();
  });
});
