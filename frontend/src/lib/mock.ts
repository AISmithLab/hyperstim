// Mock API responses for frontend work without a backend (NEXT_PUBLIC_API_MOCK=1).
// All titles and channel names are made up.
import type { ChannelSummary, ListResponse, Meta, Params, VideoSummary } from "./api";

const meta: Meta = {
  videoCount: 10412,
  channelCount: 312,
  updatedAt: "2026-09-30",
};

const videos: VideoSummary[] = [
  { id: "mockVid0001", title: "Super Turbo Rainbow Race – 40 Minutes of Non-Stop Surprise Eggs and Racing Cars Compilation", channel: "Zippy Zoom Kids", score: 97.4 },
  { id: "mockVid0002", title: "Crazy Color Blast Dance Party!!", channel: "Bouncy Beats TV", score: 95.1 },
  { id: "mockVid0003", title: "Mega Monster Truck Jump Challenge", channel: "Zippy Zoom Kids", score: 93.8 },
  { id: "mockVid0004", title: "Wiggle Pop Numbers Song", channel: "Bouncy Beats TV", score: 91.2 },
  { id: "mockVid0005", title: "Fizzy the Robot Saves the Candy Factory", channel: "Sparkle Pop Studio", score: 88.6 },
  { id: "mockVid0006", title: "Animal Sounds Speed Round", channel: "Little Paws Play", score: 71.3 },
  { id: "mockVid0007", title: "Counting Clouds with Mr. Moss", channel: "Puddle Lane", score: 42.9 },
  { id: "mockVid0008", title: "Building a Treehouse Step by Step", channel: "Maple Corner", score: 33.5 },
  { id: "mockVid0009", title: "Bedtime Story: The Sleepy Lighthouse", channel: "Quiet Meadow Tales", score: 12.4 },
  { id: "mockVid0010", title: "Watching Snails in the Garden", channel: "Puddle Lane", score: 6.8 },
];

const channels: ChannelSummary[] = [
  { name: "Zippy Zoom Kids", score: 89.7, videoCount: 48 },
  { name: "Bouncy Beats TV", score: 86.2, videoCount: 112 },
  { name: "Sparkle Pop Studio", score: 79.4, videoCount: 23 },
  { name: "Little Paws Play", score: 64.0, videoCount: 9 },
  { name: "Maple Corner", score: 38.1, videoCount: 17 },
  { name: "Puddle Lane", score: 24.6, videoCount: 31 },
  { name: "Quiet Meadow Tales", score: 15.3, videoCount: 3 },
  { name: "Tumble Town", score: 58.2, videoCount: 14 },
  { name: "Starry Song Club", score: 47.5, videoCount: 26 },
  { name: "Pebble & Pine", score: 19.8, videoCount: 11 },
];

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
      throw new Error(`No mock for ${path}`);
  }
}
