import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useSyncExternalStore } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getChannels, getVideos, type ListParams, type RankedChannel, type RankedVideo } from "@/lib/api";
import { FEATURE_GROUPS } from "@/lib/features";
import RankingsPage from "./RankingsPage";

// The URL: router calls change it, and the page re-reads it, as in the browser.
const url = vi.hoisted(() => {
  let search = new URLSearchParams();
  const listeners = new Set<() => void>();
  const navigate = (href: string) => {
    search = new URLSearchParams(href.split("?")[1] ?? "");
    listeners.forEach((l) => l());
  };
  return {
    get search() {
      return search;
    },
    subscribe: (l: () => void) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    navigate,
    push: vi.fn(navigate),
    replace: vi.fn(navigate),
  };
});
vi.mock("next/navigation", () => ({
  useSearchParams: () => useSyncExternalStore(url.subscribe, () => url.search),
  useRouter: () => ({ push: url.push, replace: url.replace }),
}));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getVideos: vi.fn(),
  getChannels: vi.fn(),
}));

const KEYS = FEATURE_GROUPS.flatMap((g) => g.keys);

function video(n: number): RankedVideo {
  return {
    id: `video${String(n).padStart(6, "0")}`,
    title: `Tiny Trucks ${n}`,
    channelId: `UCchan${n}`,
    channel: `Channel ${n}`,
    category: "music",
    rank: n,
    score: Math.max(0, 100 - n),
    features: KEYS.map((key) =>
      key === "lstar_flash_per_min" && n === 2
        ? { key, value: 0, percentile: 58.3 } // no events: "None detected"
        : { key, value: 1.5, percentile: 50 },
    ),
  };
}

const channel = (n: number): RankedChannel => ({
  id: `UCchan${n}`,
  name: `Channel ${n}`,
  videoCount: 12,
  rank: n,
  score: 80 - n,
  features: KEYS.map((key) => ({ key, value: 1, percentile: 40 })),
});

/** A ranking of `total` items, sliced by `offset`/`limit` as the API does. */
function list<T>(make: (n: number) => T, total: number) {
  return async ({ offset = 0, limit }: ListParams) => ({
    items: Array.from({ length: Math.max(0, Math.min(limit, total - offset)) }, (_, i) => make(offset + i + 1)),
    total,
  });
}

// The table and the cards (and chips and select) are both rendered; CSS shows one by width,
// which jsdom doesn't apply, so tests look inside the one they mean.
const table = () => screen.getByRole("table");
const cards = () => screen.getByRole("list", { name: /ranked by/ });
const busy = (element: HTMLElement) => element.closest("[aria-busy]");
/** The order button on the category row (`lg`+), or the one next to "Rank by" (below). */
const orderButton = (where: "wide" | "narrow") =>
  screen.getAllByRole("button", { name: /^Order:/ }).find((b) => b.classList.contains("lg:flex") === (where === "wide"))!;

function open(query = "") {
  url.navigate(`/rankings?${query}`);
  return render(<RankingsPage />);
}

const lastCall = <T,>(fn: { mock: { calls: T[][] } }) => fn.mock.calls.at(-1)?.[0];

beforeEach(() => {
  url.push.mockClear();
  url.replace.mockClear();
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("reduced-motion"), media: query }));
  vi.mocked(getVideos).mockReset().mockImplementation(list(video, 60));
  vi.mocked(getChannels).mockReset().mockImplementation(list(channel, 30));
});

describe("RankingsPage", () => {
  it("shows the first page of videos ranked by Overall", async () => {
    open();

    const table = await screen.findByRole("table", { name: "Videos, ranked by Overall, most intense first" });
    expect(getVideos).toHaveBeenLastCalledWith({
      sort: "score",
      order: "desc",
      category: "",
      q: "",
      offset: 0,
      limit: 25,
    });
    expect(screen.getByText("Showing 1–25 of 60 videos")).toBeInTheDocument();
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(2 + 25); // two header rows
    const first = rows[2];
    expect(within(first).getByRole("link", { name: "Tiny Trucks 1" })).toHaveAttribute("href", "/video?id=video000001");
    expect(within(first).getByRole("link", { name: "Channel 1" })).toHaveAttribute("href", "/channel?id=UCchan1");
    // Rank, name, Overall, then the 12.
    expect(within(first).getAllByRole("cell")).toHaveLength(15);
    expect(first.querySelectorAll("[data-filled]")[0]).toHaveTextContent("99");
    expect(first.querySelectorAll("[data-filled]")[0]).toHaveAttribute("data-filled", "5");
    expect(first.querySelectorAll("[data-filled]")[1]).toHaveAttribute("data-filled", "3");
    // No events: a dash that reads its reason.
    expect(within(rows[3]).getByText("None detected")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Overall" })).toHaveAttribute("aria-sort", "descending");
    expect(screen.getByRole("columnheader", { name: "Pacing intensification" })).toBeInTheDocument();
  });

  it("ranks by a clicked column, and flips the order on a second click", async () => {
    const user = userEvent.setup();
    open();
    await screen.findByRole("table");

    await user.click(screen.getByRole("button", { name: "Rapid cutting" }));
    expect(lastCall(url.push)).toBe("/rankings?sort=cuts_per_min");
    expect(screen.getByRole("columnheader", { name: "Rapid cutting" })).toHaveAttribute("aria-sort", "descending");
    expect(screen.getByRole("columnheader", { name: "Overall" })).not.toHaveAttribute("aria-sort");
    await waitFor(() => expect(lastCall(vi.mocked(getVideos))).toMatchObject({ sort: "cuts_per_min", order: "desc" }));

    await user.click(screen.getByRole("button", { name: "Rapid cutting" }));
    expect(lastCall(url.push)).toBe("/rankings?sort=cuts_per_min&order=asc");
    expect(screen.getByRole("columnheader", { name: "Rapid cutting" })).toHaveAttribute("aria-sort", "ascending");
    await waitFor(() => expect(lastCall(vi.mocked(getVideos))).toMatchObject({ sort: "cuts_per_min", order: "asc" }));
    expect(await screen.findByRole("table", { name: "Videos, ranked by Rapid cutting, calmest first" })).toBeInTheDocument();
  });

  it("counts back from the calm end when calmest first: −1, −2, …", async () => {
    open("order=asc");
    await screen.findByRole("table");
    const rows = within(table()).getAllByRole("row");
    expect(within(rows[2]).getByText("−1")).toBeInTheDocument();
    expect(within(rows[2]).getByText("1st calmest")).toBeInTheDocument();
    expect(within(rows[12]).getByText("11th calmest")).toBeInTheDocument();
    expect(within(rows[23]).getByText("22nd calmest")).toBeInTheDocument();
    expect(within(cards()).getByText("−3")).toBeInTheDocument();
  });

  it("flips the order with the order button next to the category chips", async () => {
    const user = userEvent.setup();
    open("sort=lufs");
    await screen.findByRole("table");

    expect(orderButton("wide")).toHaveAccessibleName("Order: Most intense first");
    await user.click(orderButton("wide"));
    expect(lastCall(url.push)).toBe("/rankings?sort=lufs&order=asc");
    expect(screen.getByRole("columnheader", { name: "Audio intensity" })).toHaveAttribute("aria-sort", "ascending");

    expect(orderButton("wide")).toHaveAccessibleName("Order: Calmest first");
    await user.click(orderButton("wide"));
    expect(lastCall(url.push)).toBe("/rankings?sort=lufs");
  });

  it("keeps calmest first when ranking by another column", async () => {
    const user = userEvent.setup();
    open("order=asc");
    await screen.findByRole("table");

    await user.click(screen.getByRole("button", { name: "Rapid cutting" }));
    expect(lastCall(url.push)).toBe("/rankings?sort=cuts_per_min&order=asc");
    expect(screen.getByRole("columnheader", { name: "Rapid cutting" })).toHaveAttribute("aria-sort", "ascending");

    await user.selectOptions(screen.getByRole("combobox", { name: "Rank by" }), "lufs");
    expect(lastCall(url.push)).toBe("/rankings?sort=lufs&order=asc");
  });

  it("shows a dash for rows without a rank", async () => {
    vi.mocked(getVideos).mockImplementation(async () => ({ items: [{ ...video(1), rank: null }], total: 1 }));
    open();

    await screen.findByRole("table");
    expect(within(table()).getByText("Not ranked")).toBeInTheDocument();
    expect(within(cards()).getByText("Not ranked")).toBeInTheDocument();
  });

  it("switches to channels, keeping search, category and criterion, back to page 1", async () => {
    const user = userEvent.setup();
    open("q=zip&category=music&sort=lufs&page=2");
    await screen.findByRole("table");

    await user.click(screen.getByRole("button", { name: "Channels" }));

    expect(lastCall(url.push)).toBe("/rankings?view=channels&sort=lufs&category=music&q=zip");
    await screen.findByRole("table", { name: "Channels, ranked by Audio intensity, most intense first" });
    expect(getChannels).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort: "lufs", category: "music", q: "zip", offset: 0, minVideos: 5 }),
    );
    expect(within(table()).getByRole("link", { name: "Channel 1" })).toHaveAttribute("href", "/channel?id=UCchan1");
    expect(within(table()).getAllByText("12 videos")).toHaveLength(25);
    expect(
      screen.getByText("Showing 1–25 of 30 channels with music videos matching “zip”"),
    ).toBeInTheDocument();
  });

  it("searches after a pause in typing, replacing the history entry", async () => {
    const user = userEvent.setup();
    open("page=2");
    await screen.findByRole("table");

    await user.type(screen.getByRole("searchbox", { name: "Search videos" }), "zippy ");
    expect(url.replace).not.toHaveBeenCalled();

    await waitFor(() => expect(url.replace).toHaveBeenCalledTimes(1));
    expect(lastCall(url.replace)).toBe("/rankings?q=zippy");
    expect(url.push).not.toHaveBeenCalled();
    // The trailing space the user typed stays in the field.
    expect(screen.getByRole("searchbox")).toHaveValue("zippy ");
    await waitFor(() => expect(lastCall(vi.mocked(getVideos))).toMatchObject({ q: "zippy", offset: 0 }));
  });

  it("keeps letters typed while the URL catches up with the search", async () => {
    const user = userEvent.setup();
    // A slow navigation: the URL changes 400 ms after the search is sent.
    url.replace.mockImplementation((href: string) => void setTimeout(() => url.navigate(href), 400));
    open();
    await screen.findByRole("table");
    const box = screen.getByRole("searchbox");

    await user.type(box, "zip");
    await waitFor(() => expect(url.replace).toHaveBeenCalledTimes(1)); // "zip" sent
    await user.type(box, "py"); // typed before the URL has "zip"
    await waitFor(() => expect(url.search.get("q")).toBe("zip"));
    expect(box).toHaveValue("zippy");

    await waitFor(() => expect(url.search.get("q")).toBe("zippy"), { timeout: 2000 });
    expect(box).toHaveValue("zippy");
    url.replace.mockImplementation(url.navigate);
  });

  it("follows the URL when it changes from outside (Back)", async () => {
    open("q=zippy");
    await screen.findByRole("table");
    expect(screen.getByRole("searchbox")).toHaveValue("zippy");

    act(() => url.navigate("/rankings"));

    expect(screen.getByRole("searchbox")).toHaveValue("");
  });

  it("filters by category with chips, and with a select on phones", async () => {
    const user = userEvent.setup();
    open();
    await screen.findByRole("table");
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: "Play & activity" }));
    expect(lastCall(url.push)).toBe("/rankings?category=play");
    expect(screen.getByRole("button", { name: "Play & activity" })).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByText(/of 60 play & activity videos/)).toBeInTheDocument();
  });

  it("uses a category select below sm", async () => {
    const user = userEvent.setup();
    open();
    await screen.findByRole("list", { name: /Videos, ranked by/ });

    await user.selectOptions(screen.getByRole("combobox", { name: "Category" }), "gaming");

    expect(lastCall(url.push)).toBe("/rankings?category=gaming");
  });

  it("pages through the results and moves focus to the results line", async () => {
    const user = userEvent.setup();
    open();
    await screen.findByRole("table");
    const pages = screen.getByRole("navigation", { name: "Pages" });
    expect(within(pages).getByRole("button", { name: "Page 1" })).toHaveAttribute("aria-current", "page");
    expect(within(pages).getByRole("button", { name: "Previous page" })).toBeDisabled();

    await user.click(within(pages).getByRole("button", { name: "Next page" }));

    expect(lastCall(url.push)).toBe("/rankings?page=2");
    const line = await screen.findByText("Showing 26–50 of 60 videos");
    await waitFor(() => expect(line).toHaveFocus());
    expect(lastCall(vi.mocked(getVideos))).toMatchObject({ offset: 25, limit: 25 });
    expect(within(table()).getByRole("link", { name: "Tiny Trucks 26" })).toBeInTheDocument();
  });

  it("keeps the current rows, busy, while the next page loads", async () => {
    const user = userEvent.setup();
    open();
    await screen.findByRole("table");
    vi.mocked(getVideos).mockReturnValue(new Promise(() => {}));

    await user.click(screen.getByRole("button", { name: "Page 2" }));

    expect(within(table()).getByRole("link", { name: "Tiny Trucks 1" })).toBeInTheDocument();
    expect(busy(table())).toHaveAttribute("aria-busy", "true");
  });

  it("goes to the last page from a link past the end", async () => {
    open("page=9");

    await waitFor(() => expect(lastCall(url.replace)).toBe("/rankings?page=3"));
    expect(await screen.findByText(/Showing 51–60 of 60 videos/)).toBeInTheDocument();
  });

  it("shows cards below lg, ranked with a select and the order button", async () => {
    const user = userEvent.setup();
    open("sort=cuts_per_min");

    const list = await screen.findByRole("list", { name: "Videos, ranked by Rapid cutting, most intense first" });
    const first = within(list).getAllByRole("listitem")[0];
    expect(within(first).getByText("Overall")).toBeInTheDocument();
    expect(within(first).getByText("Rapid cutting")).toBeInTheDocument();
    expect(first.querySelectorAll("[data-filled]")).toHaveLength(2);

    await user.selectOptions(screen.getByRole("combobox", { name: "Rank by" }), "overall");
    expect(lastCall(url.push)).toBe("/rankings");

    await user.click(orderButton("narrow"));
    expect(lastCall(url.push)).toBe("/rankings?order=asc");
    expect(orderButton("narrow")).toHaveTextContent("Calmest first");
  });

  it("shows a message with a clear button when nothing matches", async () => {
    const user = userEvent.setup();
    vi.mocked(getVideos).mockResolvedValue({ items: [], total: 0 });
    open("q=xyz&category=gaming");

    expect(await screen.findByText("No gaming videos match “xyz”.")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Pages" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Clear search" }));
    expect(lastCall(url.push)).toBe("/rankings?category=gaming");
  });

  it("shows a busy skeleton while loading", () => {
    vi.mocked(getVideos).mockReturnValue(new Promise(() => {}));
    open();

    expect(screen.getByRole("status")).toHaveTextContent("Loading rankings…");
    expect(busy(table())).toHaveAttribute("aria-busy", "true");
  });

  it("shows an error with a retry", async () => {
    const user = userEvent.setup();
    vi.mocked(getVideos).mockRejectedValueOnce(new Error("down"));
    open();

    expect(await screen.findByText("We couldn’t load the rankings.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByRole("table");
    expect(within(table()).getByRole("link", { name: "Tiny Trucks 1" })).toBeInTheDocument();
  });

  it("lets CSS pick the layout by width, so the first paint already fits", async () => {
    open();
    await screen.findByRole("table");
    // Table from lg, cards below; chips from sm, a select below; "Rank by" only below lg.
    expect(table().parentElement).toHaveClass("hidden", "lg:block");
    expect(cards().parentElement).toHaveClass("lg:hidden");
    expect(screen.getByRole("group", { name: "Category" }).parentElement).toHaveClass("hidden", "sm:flex");
    expect(screen.getByRole("combobox", { name: "Category" }).closest("label")).toHaveClass("sm:hidden");
    expect(orderButton("narrow").parentElement).toHaveClass("lg:hidden");
    expect(orderButton("wide")).toHaveClass("hidden", "lg:flex");
  });
});
