import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, getMeta, getVideo, type Feature, type VideoDetail } from "@/lib/api";
import { FEATURE_GROUPS } from "@/lib/features";
import VideoPage from "./VideoPage";

let search = new URLSearchParams();
vi.mock("next/navigation", () => ({ useSearchParams: () => search }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getVideo: vi.fn(),
  getMeta: vi.fn(),
}));

const ID = "dQw4w9WgXcQ";
const KEYS = FEATURE_GROUPS.flatMap((g) => g.keys);

function video(overrides: Partial<Record<string, Partial<Feature>>> = {}): VideoDetail {
  return {
    id: ID,
    title: "Tiny Trucks Race",
    channelId: "UCwheelie",
    channel: "Wheelie Friends TV",
    score: 86.6,
    features: KEYS.map((key) => ({ key, value: 1.5, percentile: 40, ...overrides[key] })),
  };
}

function open(id: string | null) {
  search = new URLSearchParams(id === null ? "" : { id });
  return render(<VideoPage />);
}

beforeEach(() => {
  // Reduced motion, so the gauge shows its final value at once.
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: true, media: query }));
  vi.mocked(getVideo).mockReset().mockResolvedValue(video());
  vi.mocked(getMeta).mockReset().mockResolvedValue({ videoCount: 16375, channelCount: 300, updatedAt: "2026-09-30" });
  document.title = "Video details - HyperStim?";
});

describe("VideoPage", () => {
  it("shows the score, the 12 measurements and sets the title", async () => {
    open(ID);

    expect(await screen.findByRole("heading", { level: 1, name: "Tiny Trucks Race" })).toBeInTheDocument();
    expect(getVideo).toHaveBeenCalledWith(ID);
    expect(screen.getByRole("link", { name: "Wheelie Friends TV" })).toHaveAttribute("href", "/channel?id=UCwheelie");
    expect(screen.queryByRole("link", { name: /Watch on YouTube/ })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Stimulation score" })).toHaveClass("sr-only");
    expect(screen.getByRole("button", { name: "About the stimulation score" })).toBeInTheDocument();
    expect(screen.getByText("Stimulation score 87 out of 100")).toBeInTheDocument();
    expect(screen.queryByText(/More intense than/)).not.toBeInTheDocument();
    expect(screen.getAllByText("Higher than 40% of videos in our dataset")).toHaveLength(12);
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual([
      "Pacing intensification",
      "Sustained sensory intensity",
      "Reward patterning",
    ]);
    expect(screen.getByRole("button", { name: "Play video: Tiny Trucks Race" })).toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe("Tiny Trucks Race - HyperStim?"));
  });

  it("shows the value with the description in the info popover", async () => {
    const user = userEvent.setup();
    open(ID);
    await user.click(await screen.findByRole("button", { name: "About Rapid cutting" }));
    expect(screen.getByText("How often the picture switches to a new shot.")).toBeVisible();
    expect(screen.getByText("1.5 cuts per minute")).toBeVisible();
  });

  it("shows None detected, No cuts and Not measured", async () => {
    vi.mocked(getVideo).mockResolvedValue(
      video({
        build_resolve_per_min: { value: 0, percentile: 62 },
        inter_cut_dssim_mean: { value: null, percentile: null },
        lufs: { value: null, percentile: null },
      }),
    );
    open(ID);
    expect(await screen.findByText("None detected")).toBeInTheDocument();
    expect(screen.getByText("No cuts")).toBeInTheDocument();
    expect(screen.getByText("Not measured")).toBeInTheDocument();
    expect(screen.getAllByText(/^Higher than/)).toHaveLength(9);
  });

  it("shows the kid peeking over the score panel", async () => {
    const { container } = open(ID);
    await screen.findByRole("heading", { level: 1, name: "Tiny Trucks Race" });
    const kid = container.querySelector("img[data-kid]");
    expect(kid).toHaveAttribute("src", "/images/kid_3.webp");
    expect(kid).toHaveAttribute("alt", "");
  });

  it("shows a busy skeleton while loading", () => {
    vi.mocked(getVideo).mockReturnValue(new Promise(() => {}));
    const { container } = open(ID);
    expect(screen.getByRole("status")).toHaveTextContent("Loading video…");
    expect(container.querySelector("[aria-busy=true]")).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("iframe")).toBeNull();
  });

  it.each([null, "", "short", `https://youtu.be/${ID}`])("rejects the ID %j", (id) => {
    open(id);
    expect(screen.getByText("That doesn’t look like a YouTube video ID.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Check another video/ })).toHaveAttribute("href", "/");
    expect(getVideo).not.toHaveBeenCalled();
  });

  it("says when the video isn't in the dataset", async () => {
    vi.mocked(getVideo).mockRejectedValue(new ApiError(404, "Video not found"));
    open(ID);
    expect(
      await screen.findByRole("heading", { level: 1, name: "We haven’t checked this video yet" }),
    ).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/It isn’t one of the 16,375 videos/)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /Check another video/ })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: /Watch on YouTube/ })).toBeInTheDocument();
  });

  it("shows an error with a retry that reloads", async () => {
    const user = userEvent.setup();
    vi.mocked(getVideo).mockRejectedValueOnce(new ApiError(500, "down"));
    open(ID);
    expect(await screen.findByText("We couldn’t load this video.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Tiny Trucks Race" })).toBeInTheDocument();
  });
});
