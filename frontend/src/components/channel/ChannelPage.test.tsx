import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, getChannel, type ChannelDetail, type ChannelVideo } from "@/lib/api";
import { FEATURE_GROUPS } from "@/lib/features";
import ChannelPage from "./ChannelPage";

let search = new URLSearchParams();
vi.mock("next/navigation", () => ({ useSearchParams: () => search }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getChannel: vi.fn(),
}));

const ID = "UC" + "x".repeat(22);
const KEYS = FEATURE_GROUPS.flatMap((g) => g.keys);

function video(n: number, publishedAt: string, overrides: Record<string, [number | null, number | null]> = {}): ChannelVideo {
  return {
    id: `video00000${n}`,
    title: `Tiny Trucks ${n}`,
    publishedAt,
    score: 10 * n,
    features: KEYS.map((key) => {
      const [value, percentile] = overrides[key] ?? [1.5, 5 * n];
      return { key, value, percentile };
    }),
  };
}

function channel(videos = [
  video(1, "2018-02-03", { lstar_flash_per_min: [0, 0] }),
  video(2, "2020-05-01", { lufs: [null, null] }),
  video(3, "2024-09-06", { lstar_flash_per_min: [0, 0], lufs: [null, null] }),
  video(4, "2026-01-10", { inter_cut_dssim_mean: [null, null] }),
]): ChannelDetail {
  return {
    id: ID,
    name: "Wheelie Friends TV",
    videoCount: videos.length,
    score: 74.2,
    features: KEYS.map((key) => ({ key, value: 1.6, percentile: 61 })),
    videos,
  };
}

/** Stubs media queries: phones (below sm) or wider; always reduced motion. */
function screenWidth(wide: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("reduced-motion") || wide,
    media: query,
  }));
}

function open(id: string | null) {
  search = new URLSearchParams(id === null ? "" : { id });
  return render(<ChannelPage />);
}

const loaded = () => screen.findByRole("heading", { level: 1, name: "Wheelie Friends TV" });
const table = () => screen.getByRole("table", { name: "Wheelie Friends TV’s videos over the years" });

beforeEach(() => {
  screenWidth(true);
  vi.mocked(getChannel).mockReset().mockResolvedValue(channel());
  document.title = "Channel details - HyperStim?";
});

describe("ChannelPage", () => {
  it("shows the channel, its score and measurements, and sets the title", async () => {
    const { container } = open(ID);
    await loaded();
    expect(getChannel).toHaveBeenCalledWith(ID);
    expect(screen.getByText("4 videos in our dataset · 2018–2026")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /View on YouTube/ })).toHaveAttribute(
      "href",
      `https://www.youtube.com/channel/${ID}`,
    );
    expect(screen.getByRole("link", { name: /Compare with another channel/ })).toHaveAttribute(
      "href",
      `/compare?view=channels&a=${ID}`,
    );
    expect(screen.getByText("Stimulation score 74 out of 100")).toBeInTheDocument();
    expect(screen.getAllByText("Higher than 61% of videos in our dataset")).toHaveLength(12);
    expect(screen.queryByText(/^#/)).not.toBeInTheDocument(); // no rank
    expect(container.querySelector("img[data-kid]")).toHaveAttribute("src", "/images/kid_lens_downward.webp");
    await waitFor(() => expect(document.title).toBe("Wheelie Friends TV - HyperStim?"));
  });

  it("says the channel's values are averages in the popovers", async () => {
    const user = userEvent.setup();
    open(ID);
    await loaded();
    await user.click(screen.getByRole("button", { name: "About Luminance flash" }));
    const popover = document.getElementById("feature-lstar_flash_per_min")!;
    expect(popover).toBeVisible();
    expect(popover).toHaveTextContent("This channel: 1.6 per minute on average");
  });

  it("says the score is about production style only", async () => {
    const user = userEvent.setup();
    open(ID);
    await loaded();
    await user.click(screen.getByRole("button", { name: "About the stimulation score" }));
    expect(screen.getByText(/We measure production style only\./)).toBeVisible();
    expect(screen.queryByText(/good or bad/)).not.toBeInTheDocument();
  });

  it("charts the overall score by default, with a dot per video and a trend line", async () => {
    const { container } = open(ID);
    await loaded();
    expect(screen.getByRole("heading", { level: 2, name: "How it changed over years?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Overall", pressed: true })).toBeInTheDocument();
    expect(container.querySelectorAll("[data-dot]")).toHaveLength(4);
    expect(container.querySelector("[data-trend]")).toBeInTheDocument();
    expect(container.querySelector("[data-chart] svg")).toHaveAttribute("aria-hidden", "true");
    const rows = within(table()).getAllByRole("row");
    expect(rows[0]).toHaveTextContent("PublishedVideoOverall");
    expect(rows[1]).toHaveTextContent("Feb 3, 2018Tiny Trucks 110");
    expect(screen.queryByText(/not measured$/)).not.toBeInTheDocument();
  });

  it("switches the measurement with the chips, one at a time", async () => {
    const user = userEvent.setup();
    const { container } = open(ID);
    await loaded();
    const chips = within(screen.getByRole("group", { name: "Show" }));
    const height = () => container.querySelector("[data-chart] svg")!.getAttribute("height");
    const overallHeight = height();
    await user.click(chips.getByRole("button", { name: "Luminance flash" }));
    expect(height()).toBe(overallHeight);
    expect(chips.getByRole("button", { name: "Luminance flash", pressed: true })).toBeInTheDocument();
    expect(chips.getAllByRole("button", { pressed: true })).toHaveLength(1);
    // Two videos with a count of 0 are plain dots at 0, counted in the trend.
    expect(container.querySelectorAll("[data-dot]")).toHaveLength(4);
    expect(container.querySelector("[data-trend]")).toBeInTheDocument();
    expect(within(table()).getAllByRole("row")[1]).toHaveTextContent("Feb 3, 2018Tiny Trucks 10");

    // No cuts: a ×, left out of the trend (3 videos remain), and not counted as not measured.
    await user.click(chips.getByRole("button", { name: "Scene discontinuity" }));
    expect(container.querySelectorAll('[data-mark="na"]')).toHaveLength(1);
    expect(container.querySelectorAll("[data-dot]")).toHaveLength(4);
    expect(container.querySelector("[data-trend]")).toBeInTheDocument();
    expect(screen.queryByText(/not measured$/)).not.toBeInTheDocument();
    expect(within(table()).getAllByRole("row")[4]).toHaveTextContent("Jan 10, 2026Tiny Trucks 4No cuts");

    await user.click(chips.getByRole("button", { name: "Audio intensity" }));
    expect(container.querySelectorAll("[data-dot]")).toHaveLength(2);
    expect(screen.getByText("2 videos without sound")).toBeInTheDocument();
    expect(within(table()).getAllByRole("columnheader")[2]).toHaveTextContent("Audio intensity");
  });

  it("opens a video in the panel from its thumbnail, replaces it, and closes back to the thumbnail", async () => {
    const user = userEvent.setup();
    const { container } = open(ID);
    await loaded();
    const thumb = screen.getByRole("button", { name: "Tiny Trucks 3, Sep 6, 2024" });
    expect(thumb.querySelector("img")).toHaveAttribute("loading", "lazy");
    expect(container.querySelector("iframe")).toBeNull();

    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    await user.click(thumb);
    const panel = screen.getByRole("region", { name: "Tiny Trucks 3" });
    expect(panel).toHaveFocus();
    // Scrolled into view (at once: the tests run with reduced motion), not playing yet.
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "auto", block: "nearest" });
    expect(panel.querySelector("iframe")).toBeNull();
    expect(within(panel).getByRole("button", { name: "Play video: Tiny Trucks 3" })).toBeInTheDocument();
    expect(within(panel).getByText("Sep 6, 2024")).toBeInTheDocument();
    expect(within(panel).getByText("Overall")).toBeInTheDocument();
    expect(within(panel).getByText("30")).toBeInTheDocument();
    expect(within(panel).getByRole("link", { name: /Video details/ })).toHaveAttribute("href", "/video?id=video000003");
    expect(thumb).toHaveAttribute("aria-current", "true");

    // Changing the measurement keeps the panel and updates its value.
    await user.click(screen.getByRole("button", { name: "Luminance flash" }));
    expect(within(screen.getByRole("region", { name: "Tiny Trucks 3" })).getByText("0")).toBeInTheDocument();

    // A dot opens its video in place of the first.
    fireEvent.click(container.querySelector('[data-hit="video000001"]')!);
    expect(screen.queryByRole("region", { name: "Tiny Trucks 3" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Tiny Trucks 1" })).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("region", { name: /^Tiny Trucks/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tiny Trucks 1, Feb 3, 2018" })).toHaveFocus();
  });

  it("shows the same popover for a hovered dot or thumbnail", async () => {
    const { container } = open(ID);
    await loaded();
    fireEvent.pointerEnter(container.querySelector('[data-hit="video000002"]')!, { pointerType: "mouse" });
    const popover = container.querySelector("[data-popover]");
    expect(popover).toHaveTextContent("“Tiny Trucks 2”May 1, 2020Overall:20");
    expect(popover?.querySelector("[data-filled]")).toHaveAttribute("data-filled", "1"); // the meter, after the number
    expect(container.querySelector('[data-dot="video000002"]')).toHaveAttribute("r", "7");
    // Its thumbnail stands out of its stack.
    expect(screen.getByRole("button", { name: "Tiny Trucks 2, May 1, 2020" })).toHaveClass("scale-108");
    fireEvent.pointerLeave(container.querySelector('[data-hit="video000002"]')!, { pointerType: "mouse" });
    expect(container.querySelector("[data-popover]")).toBeNull();
    fireEvent.pointerEnter(screen.getByRole("button", { name: "Tiny Trucks 2, May 1, 2020" }), { pointerType: "mouse" });
    expect(container.querySelector("[data-popover]")).toHaveTextContent("“Tiny Trucks 2”May 1, 2020Overall:20");
  });

  it("says 1 video and one year for a single video", async () => {
    vi.mocked(getChannel).mockResolvedValue(channel([video(1, "2024-03-02")]));
    const { container } = open(ID);
    await loaded();
    expect(screen.getByText("1 video in our dataset · 2024")).toBeInTheDocument();
    expect(container.querySelectorAll("[data-dot]")).toHaveLength(1);
    expect(container.querySelector("[data-trend]")).toBeNull();
  });

  it("shows a busy skeleton while loading", () => {
    vi.mocked(getChannel).mockReturnValue(new Promise(() => {}));
    const { container } = open(ID);
    expect(screen.getByRole("status")).toHaveTextContent("Loading channel…");
    expect(container.querySelector("[aria-busy=true]")).toBeInTheDocument();
  });

  it.each([null, "", "UCshort", "XY" + "x".repeat(22), `https://www.youtube.com/channel/${ID}`])(
    "rejects the ID %j",
    (id) => {
      open(id);
      expect(screen.getByText("That doesn’t look like a channel link.")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Check a video/ })).toHaveAttribute("href", "/");
      expect(getChannel).not.toHaveBeenCalled();
    },
  );

  it("says when the channel isn't in the dataset", async () => {
    vi.mocked(getChannel).mockRejectedValue(new ApiError(404, "Channel not found"));
    const { container } = open(ID);
    expect(await screen.findByText("This channel isn’t in our dataset.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Check a video/ })).toHaveAttribute("href", "/");
    expect(container.querySelector("img[data-kid]")).toHaveAttribute("src", "/images/kid_2.webp");
  });

  it("shows an error with a retry that reloads", async () => {
    const user = userEvent.setup();
    vi.mocked(getChannel).mockRejectedValueOnce(new ApiError(500, "down"));
    open(ID);
    expect(await screen.findByText("We couldn’t load this channel.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await loaded()).toBeInTheDocument();
  });
});

describe("ChannelPage on phones", () => {
  beforeEach(() => screenWidth(false));

  /** Lays the strip's cards out 160 px apart in a 320 px wide scroller, scrolled to `scrollLeft`. */
  function layOut(list: HTMLElement, scrollLeft: number) {
    const cards = [...list.children] as HTMLElement[];
    cards.forEach((card, i) => {
      Object.defineProperty(card, "offsetLeft", { configurable: true, value: i * 160 });
      Object.defineProperty(card, "offsetWidth", { configurable: true, value: 160 });
    });
    Object.defineProperty(list, "clientWidth", { configurable: true, value: 320 });
    Object.defineProperty(list, "scrollWidth", { configurable: true, value: cards.length * 160 });
    list.scrollLeft = scrollLeft;
    fireEvent.scroll(list);
  }

  it("picks the measurement with a select, and has no thumbnails or panel", async () => {
    const user = userEvent.setup();
    const { container } = open(ID);
    await loaded();
    expect(screen.queryByRole("group", { name: "Show" })).not.toBeInTheDocument();
    const select = screen.getByRole("combobox", { name: "Show" });
    expect(select).toHaveValue("overall");
    await user.selectOptions(select, "lufs");
    expect(within(table()).getAllByRole("columnheader")[2]).toHaveTextContent("Audio intensity");
    expect(container.querySelector("[id^=thumb-]")).toBeNull();
    fireEvent.click(container.querySelector('[data-hit="video000001"]')!);
    expect(screen.queryByRole("region", { name: /^Tiny Trucks/ })).not.toBeInTheDocument();
  });

  it("lists the videos as cards linking to their pages, with a band for the ones in view", async () => {
    const { container } = open(ID);
    await loaded();
    const strip = screen.getByRole("heading", { level: 3, name: "The 4 videos we measured" }).closest("section")!;
    const cards = within(strip).getAllByRole("link");
    expect(cards.map((a) => a.getAttribute("aria-label"))).toEqual([
      "Tiny Trucks 1, Feb 3, 2018",
      "Tiny Trucks 2, May 1, 2020",
      "Tiny Trucks 3, Sep 6, 2024",
      "Tiny Trucks 4, Jan 10, 2026",
    ]);
    expect(cards[0]).toHaveAttribute("href", "/video?id=video000001");

    const list = within(strip).getByRole("list");
    const older = within(strip).getByRole("button", { name: "Older videos" });
    const newer = within(strip).getByRole("button", { name: "Newer videos" });
    layOut(list, 0);
    expect(older).toBeDisabled();
    expect(newer).toBeEnabled();
    const band = () => container.querySelector("[data-band]");
    const first = Number(band()?.getAttribute("x"));
    layOut(list, 320);
    expect(older).toBeEnabled();
    expect(newer).toBeDisabled();
    expect(Number(band()?.getAttribute("x"))).toBeGreaterThan(first);
  });

  it("scrolls to and marks a tapped dot's card, with its popover", async () => {
    const { container } = open(ID);
    await loaded();
    const list = screen.getAllByRole("list").at(-1)!;
    const scrollTo = vi.fn();
    list.scrollTo = scrollTo;
    layOut(list, 0);
    fireEvent.click(container.querySelector('[data-hit="video000003"]')!);
    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ left: 320 }));
    expect(screen.getByRole("link", { name: "Tiny Trucks 3, Sep 6, 2024" })).toHaveClass("bg-sky");
    expect(container.querySelector("[data-popover]")).toHaveTextContent("Tiny Trucks 3");
  });
});
