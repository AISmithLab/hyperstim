// Mock API responses for frontend work without a backend (NEXT_PUBLIC_API_MOCK=1).
// All titles and channel names are made up. Video pages: mockVid0500 returns a server error;
// any other ID that isn't a mock video is analyzed live in ~12 s, then has a result. Live
// analysis: mockVidWait waits in the queue first; the IDs in MOCK_FAILURES fail with their
// error; mockVidBusy gets 503 (queue full) and mockVid0429 gets 429 (limit reached). Channel
// pages: every mock channel has generated videos (Zippy Zoom Kids: 60 over many years; Little
// Paws Play: one year; Quiet Meadow Tales: one video; Puddle Lane: zero events and missing
// values); MOCK_CHANNEL_ERROR returns a server error; any other channel ID is not found.
import {
  ApiError,
  type Analysis,
  type AnalysisErrorCode,
  type AnalysisStatus,
  type ChannelDetail,
  type ChannelSummary,
  type ChannelVideo,
  type Feature,
  type ListResponse,
  type Meta,
  type Method,
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
  { id: "mockVid0001", title: "Super Turbo Rainbow Race – 40 Minutes of Non-Stop Surprise Eggs and Racing Cars Compilation", channelId: "UCmockZippyZoomKids00000", channel: "Zippy Zoom Kids", score: 97.4 },
  { id: "mockVid0002", title: "Crazy Color Blast Dance Party!!", channelId: "UCmockBouncyBeatsTv00000", channel: "Bouncy Beats TV", score: 95.1 },
  { id: "mockVid0003", title: "Mega Monster Truck Jump Challenge", channelId: "UCmockZippyZoomKids00000", channel: "Zippy Zoom Kids", score: 93.8 },
  { id: "mockVid0004", title: "Wiggle Pop Numbers Song", channelId: "UCmockBouncyBeatsTv00000", channel: "Bouncy Beats TV", score: 91.2 },
  { id: "mockVid0005", title: "Fizzy the Robot Saves the Candy Factory", channelId: "UCmockSparklePopStudio00", channel: "Sparkle Pop Studio", score: 88.6 },
  { id: "mockVid0006", title: "Animal Sounds Speed Round", channelId: "UCmockLittlePawsPlay0000", channel: "Little Paws Play", score: 71.3 },
  { id: "mockVid0007", title: "Counting Clouds with Mr. Moss", channelId: "UCmockPuddleLane00000000", channel: "Puddle Lane", score: 42.9 },
  { id: "mockVid0008", title: "Building a Treehouse Step by Step", channelId: "UCmockMapleCorner0000000", channel: "Maple Corner", score: 33.5 },
  { id: "mockVid0009", title: "Bedtime Story: The Sleepy Lighthouse", channelId: "UCmockQuietMeadowTales00", channel: "Quiet Meadow Tales", score: 12.4 },
  { id: "mockVid0010", title: "Watching Snails in the Garden", channelId: "UCmockPuddleLane00000000", channel: "Puddle Lane", score: 6.8 },
];

const channels: ChannelSummary[] = [
  { id: "UCmockZippyZoomKids00000", name: "Zippy Zoom Kids", score: 89.7, videoCount: 60 },
  { id: "UCmockBouncyBeatsTv00000", name: "Bouncy Beats TV", score: 86.2, videoCount: 60 },
  { id: "UCmockSparklePopStudio00", name: "Sparkle Pop Studio", score: 79.4, videoCount: 23 },
  { id: "UCmockLittlePawsPlay0000", name: "Little Paws Play", score: 64.0, videoCount: 9 },
  { id: "UCmockMapleCorner0000000", name: "Maple Corner", score: 38.1, videoCount: 17 },
  { id: "UCmockPuddleLane00000000", name: "Puddle Lane", score: 24.6, videoCount: 14 },
  { id: "UCmockQuietMeadowTales00", name: "Quiet Meadow Tales", score: 15.3, videoCount: 1 },
  { id: "UCmockTumbleTown00000000", name: "Tumble Town", score: 58.2, videoCount: 14 },
  { id: "UCmockStarrySongClub0000", name: "Starry Song Club", score: 47.5, videoCount: 26 },
  { id: "UCmockPebblePine00000000", name: "Pebble & Pine", score: 19.8, videoCount: 11 },
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
  if (video) return { ...video, channelInDataset: true, features: mockFeatures(video.score, featureOverrides[id]) };
  for (const channel of channels) {
    const found = channelVideos(channel).find((v) => v.id === id);
    if (found) {
      const { id, title, score, features } = found;
      return { id, title, score, features, channelId: channel.id, channel: channel.name, channelInDataset: true };
    }
  }
  if (analyses.has(id) && mockAnalysis(id).status === "done") {
    const live = { id, title: LIVE_TITLE, channelId: "UCmockFreshFinds00000000", channel: "Fresh Finds", score: 64.2 };
    return { ...live, channelInDataset: false, features: mockFeatures(live.score) };
  }
  throw new ApiError(404, "Video not found");
}

const LIVE_TITLE = "Jelly Bean Jungle Adventure – Mock Video Checked Live";
// Seconds per step, shorter than the real ones (~6, 15 and 25 s) so the flow is quick to try.
const MOCK_STEPS: [AnalysisStatus, number][] = [
  ["lookup", 2],
  ["download", 4],
  ["measure", 6],
];
const MOCK_WAIT_S = 4; // mockVidWait's time in the queue
// IDs that fail after the look-up, one per error.
const MOCK_FAILURES: Record<string, AnalysisErrorCode> = {
  mockVidFail: "unavailable",
  mockNotKids: "not_for_kids",
  mockVidShrt: "too_short",
  mockVidLive: "live",
  mockVidErrr: "failed",
};
const analyses = new Map<string, number>(); // ID -> start time (ms)

function mockAnalysis(id: string): Analysis {
  const base = { queuePosition: null, remainingS: null, error: null };
  let elapsed = (Date.now() - (analyses.get(id) ?? Date.now())) / 1000;
  const wait = id === "mockVidWait" ? MOCK_WAIT_S : 0;
  if (elapsed < wait) {
    return { ...base, status: "queued", queuePosition: Math.ceil((wait - elapsed) / 2), progress: 0 };
  }
  elapsed -= wait;
  const error = MOCK_FAILURES[id];
  if (error && elapsed > MOCK_STEPS[0][1]) return { ...base, status: "failed", progress: 0, error };
  const total = MOCK_STEPS.reduce((sum, [, s]) => sum + s, 0);
  let before = 0;
  for (const [status, seconds] of MOCK_STEPS) {
    if (elapsed < before + seconds) {
      const within = elapsed - before;
      return {
        ...base,
        status,
        progress: (before + Math.min(within, seconds * 0.9)) / total,
        remainingS: Math.round(total - before - Math.min(within, seconds * 0.9)),
      };
    }
    before += seconds;
  }
  return { ...base, status: "done", progress: 1 };
}

function analysisRequest(method: Method, id: string): Analysis {
  const video = videos.find((v) => v.id === id);
  if (video) return { queuePosition: null, remainingS: null, error: null, status: "done", progress: 1 };
  if (method === "POST") {
    if (id === "mockVidBusy") throw new ApiError(503, "Busy");
    if (id === "mockVid0429") throw new ApiError(429, "Too many requests");
    const current = analyses.has(id) ? mockAnalysis(id) : null;
    if (!current || current.status === "failed") analyses.set(id, Date.now());
  } else if (!analyses.has(id)) {
    throw new ApiError(404, "Analysis not found");
  }
  return mockAnalysis(id);
}

export const MOCK_CHANNEL_ERROR = "UCmockServerError0000000";

/** Deterministic pseudo-random numbers in [0, 1), so mock channels look the same on every load. */
function random(seed: string): () => number {
  let a = [...seed].reduce((h, c) => Math.imul(h ^ c.charCodeAt(0), 2654435761), 1);
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const TITLE_WORDS = [
  ["Tiny", "Giant", "Sleepy", "Speedy", "Rainbow", "Bubbly", "Silly", "Brave", "Sparkly", "Wobbly"],
  ["Trucks", "Dinosaurs", "Kittens", "Robots", "Rockets", "Ducks", "Trains", "Monsters", "Bunnies", "Pirates"],
  ["Race to the Bridge", "Learn Colors", "Go Camping", "Bake a Cake", "Find the Treasure", "Sing Along", "Count to Ten", "Clean Up", "Build a Tower", "Say Goodnight"],
];

// Channels whose mock videos follow a special pattern (see the comment at the top).
const CHANNEL_SHAPES: Record<string, { years: [number, number]; zeroEvents?: boolean }> = {
  UCmockZippyZoomKids00000: { years: [2016, 2026] },
  UCmockLittlePawsPlay0000: { years: [2024, 2024] },
  UCmockPuddleLane00000000: { years: [2019, 2023], zeroEvents: true },
};
const PER_MINUTE_EVENTS = ["lstar_flash_per_min", "build_resolve_per_min", "loudness_jump_at_cut_per_min"];

const channelVideoCache = new Map<string, ChannelVideo[]>();

/** A mock channel's videos, oldest first: dates bunched in some years, scores drifting over time. */
function channelVideos(channel: ChannelSummary): ChannelVideo[] {
  const cached = channelVideoCache.get(channel.id);
  if (cached) return cached;
  const rand = random(channel.id);
  const shape = CHANNEL_SHAPES[channel.id] ?? { years: [2019, 2025] };
  const [first, last] = shape.years;
  const start = Date.UTC(first, 0, 1);
  const span = Date.UTC(last, 11, 31) - start;
  const ownVideos = videos.filter((v) => v.channelId === channel.id);
  const result: ChannelVideo[] = Array.from({ length: channel.videoCount }, (_, i) => {
    // Squaring bunches the dates towards the later, busier years.
    const t = Math.sqrt(rand());
    const publishedAt = new Date(start + t * span).toISOString().slice(0, 10);
    const own = ownVideos[i];
    const score = own?.score ?? round1(Math.min(100, Math.max(0, channel.score + (t - 0.5) * 30 + (rand() - 0.5) * 36)));
    const features = mockFeatures(score, own ? featureOverrides[own.id] : undefined).map((f) =>
      own || f.percentile === null
        ? f
        : { ...f, percentile: round1(Math.min(100, Math.max(0, f.percentile + (rand() - 0.5) * 30))) },
    );
    if (shape.zeroEvents && !own) {
      for (const f of features) {
        if (PER_MINUTE_EVENTS.includes(f.key) && rand() < 0.4) Object.assign(f, { value: 0, percentile: 58.3 });
      }
      if (i % 6 === 2) Object.assign(features[8], { value: null, percentile: null }); // lufs not measured
    }
    const title =
      own?.title ??
      TITLE_WORDS.map((words) => words[Math.floor(rand() * words.length)]).join(" ");
    const id = own?.id ?? `mock${channel.id.slice(6, 9)}${String(i).padStart(4, "0")}`;
    return { id, title, publishedAt, score, features };
  }).sort((a, b) => a.publishedAt.localeCompare(b.publishedAt) || a.id.localeCompare(b.id));
  channelVideoCache.set(channel.id, result);
  return result;
}

const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);

function channelDetail(id: string): ChannelDetail {
  if (id === MOCK_CHANNEL_ERROR) throw new ApiError(500, "Mock server error");
  const channel = channels.find((c) => c.id === id);
  if (!channel) throw new ApiError(404, "Channel not found");
  const list = channelVideos(channel);
  const features = list[0].features.map(({ key }, i) => {
    const measured = list.map((v) => v.features[i]).filter((f) => f.value !== null);
    const value = mean(measured.map((f) => f.value ?? 0));
    const percentile = mean(measured.map((f) => f.percentile ?? 0));
    return { key, value, percentile: percentile === null ? null : round1(percentile) };
  });
  return {
    id,
    name: channel.name,
    videoCount: list.length,
    score: round1(mean(list.map((v) => v.score)) ?? 0),
    features,
    videos: list,
  };
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

export async function mockRequest(method: Method, path: string, params: Params): Promise<unknown> {
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
      if (path.startsWith("/api/channels/")) {
        return channelDetail(decodeURIComponent(path.slice("/api/channels/".length)));
      }
      if (path.startsWith("/api/analyses/")) {
        return analysisRequest(method, decodeURIComponent(path.slice("/api/analyses/".length)));
      }
      throw new Error(`No mock for ${path}`);
  }
}
