// Mock API responses for frontend work without a backend (NEXT_PUBLIC_API_MOCK=1).
// All titles and channel names are made up. Video pages: unknown IDs (e.g. mockVid0404) return
// 404, and mockVid0500 returns a server error.
import {
  ApiError,
  type ChannelSummary,
  type Feature,
  type ListResponse,
  type Meta,
  type Params,
  type VideoDetail,
  type VideoSummary,
} from "./api";

const meta: Meta = {
  videoCount: 10412,
  channelCount: 312,
  updatedAt: "2026-09-30",
};

const videos: VideoSummary[] = [
  { id: "mockVid0001", title: "Super Turbo Rainbow Race – 40 Minutes of Non-Stop Surprise Eggs and Racing Cars Compilation", channelId: "mock-zippy-zoom-kids", channel: "Zippy Zoom Kids", score: 97.4 },
  { id: "mockVid0002", title: "Crazy Color Blast Dance Party!!", channelId: "mock-bouncy-beats-tv", channel: "Bouncy Beats TV", score: 95.1 },
  { id: "mockVid0003", title: "Mega Monster Truck Jump Challenge", channelId: "mock-zippy-zoom-kids", channel: "Zippy Zoom Kids", score: 93.8 },
  { id: "mockVid0004", title: "Wiggle Pop Numbers Song", channelId: "mock-bouncy-beats-tv", channel: "Bouncy Beats TV", score: 91.2 },
  { id: "mockVid0005", title: "Fizzy the Robot Saves the Candy Factory", channelId: "mock-sparkle-pop-studio", channel: "Sparkle Pop Studio", score: 88.6 },
  { id: "mockVid0006", title: "Animal Sounds Speed Round", channelId: "mock-little-paws-play", channel: "Little Paws Play", score: 71.3 },
  { id: "mockVid0007", title: "Counting Clouds with Mr. Moss", channelId: "mock-puddle-lane", channel: "Puddle Lane", score: 42.9 },
  { id: "mockVid0008", title: "Building a Treehouse Step by Step", channelId: "mock-maple-corner", channel: "Maple Corner", score: 33.5 },
  { id: "mockVid0009", title: "Bedtime Story: The Sleepy Lighthouse", channelId: "mock-quiet-meadow-tales", channel: "Quiet Meadow Tales", score: 12.4 },
  { id: "mockVid0010", title: "Watching Snails in the Garden", channelId: "mock-puddle-lane", channel: "Puddle Lane", score: 6.8 },
];

const channels: ChannelSummary[] = [
  { id: "mock-zippy-zoom-kids", name: "Zippy Zoom Kids", score: 89.7, videoCount: 48 },
  { id: "mock-bouncy-beats-tv", name: "Bouncy Beats TV", score: 86.2, videoCount: 112 },
  { id: "mock-sparkle-pop-studio", name: "Sparkle Pop Studio", score: 79.4, videoCount: 23 },
  { id: "mock-little-paws-play", name: "Little Paws Play", score: 64.0, videoCount: 9 },
  { id: "mock-maple-corner", name: "Maple Corner", score: 38.1, videoCount: 17 },
  { id: "mock-puddle-lane", name: "Puddle Lane", score: 24.6, videoCount: 31 },
  { id: "mock-quiet-meadow-tales", name: "Quiet Meadow Tales", score: 15.3, videoCount: 3 },
  { id: "mock-tumble-town", name: "Tumble Town", score: 58.2, videoCount: 14 },
  { id: "mock-starry-song-club", name: "Starry Song Club", score: 47.5, videoCount: 26 },
  { id: "mock-pebble-pine", name: "Pebble & Pine", score: 19.8, videoCount: 11 },
];

/** Mock raw value per feature at a given percentile (rough dataset ranges). */
const FEATURE_SCALE: Record<string, (p: number) => number> = {
  cuts_per_min: (p) => p * 0.4,
  inter_cut_dssim_mean: (p) => 0.2 + p * 0.004,
  palette_change_per_min: (p) => p * 0.3,
  lstar_flash_per_min: (p) => p * 0.05,
  motion_frac: (p) => p * 0.008,
  loudness_jumps_per_min: (p) => p * 0.02,
  mean_saturation: (p) => 0.2 + p * 0.005,
  mean_lstar: (p) => 40 + p * 0.4,
  lufs: (p) => -30 + p * 0.25,
  high_lufs_frac: (p) => 0.5 + p * 0.005,
  build_resolve_per_min: (p) => p * 0.01,
  loudness_jump_at_cut_per_min: (p) => p * 0.02,
};

// Spread around the video's score so the measurements differ from each other.
const OFFSETS = [6, -9, 3, -2, -14, -7, 1, -25, 4, -18, -10, -5];

const round1 = (x: number) => Math.round(x * 10) / 10;

function mockFeatures(score: number, overrides: Record<string, number | null> = {}): Feature[] {
  return Object.entries(FEATURE_SCALE).map(([key, scale], i) => {
    if (key in overrides) {
      const value = overrides[key];
      // Ties at 0 put zero-event videos in the middle of the dataset.
      return { key, value, percentile: value === null ? null : value === 0 ? 58.3 : 50 };
    }
    const percentile = round1(Math.min(100, Math.max(0, score + OFFSETS[i])));
    return { key, value: Math.round(scale(percentile) * 1000) / 1000, percentile };
  });
}

const NO_EVENTS = { lstar_flash_per_min: 0, build_resolve_per_min: 0, loudness_jump_at_cut_per_min: 0 };

const featureOverrides: Record<string, Record<string, number | null>> = {
  // Zero-event case: shows "None detected".
  mockVid0009: NO_EVENTS,
  // Missing values: no cuts at all, and a feature that couldn't be measured.
  mockVid0010: { ...NO_EVENTS, cuts_per_min: 0, inter_cut_dssim_mean: null, lufs: null },
};

function videoDetail(id: string): VideoDetail {
  if (id === "mockVid0500") throw new ApiError(500, "Mock server error");
  const video = videos.find((v) => v.id === id);
  if (!video) throw new ApiError(404, "Video not found");
  return { ...video, features: mockFeatures(video.score, featureOverrides[id]) };
}

function list<T extends { score: number }>(
  items: T[],
  sort: string,
  limit: number,
): ListResponse<T> {
  const sign = sort === "score_asc" ? 1 : -1;
  const sorted = [...items].sort((a, b) => sign * (a.score - b.score));
  return { items: sorted.slice(0, limit), total: sorted.length };
}

export async function mockGet(path: string, params: Params): Promise<unknown> {
  // Short delay so loading states are visible during development.
  await new Promise((resolve) => setTimeout(resolve, 400));
  const limit = Number(params.limit ?? 50);
  const sort = String(params.sort ?? "score_desc");
  switch (path) {
    case "/api/meta":
      return meta;
    case "/api/videos":
      return list(videos, sort, limit);
    case "/api/channels": {
      const minVideos = Number(params.minVideos ?? 5);
      return list(
        channels.filter((c) => c.videoCount >= minVideos),
        sort,
        limit,
      );
    }
    default:
      if (path.startsWith("/api/videos/")) {
        return videoDetail(decodeURIComponent(path.slice("/api/videos/".length)));
      }
      throw new Error(`No mock for ${path}`);
  }
}
