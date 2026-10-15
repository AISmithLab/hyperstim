// Typed client for the backend API. The contract lives in backend/; change both together.

export type Meta = {
  videoCount: number;
  channelCount: number;
  /** ISO date */
  updatedAt: string;
};

export type VideoSummary = {
  id: string;
  title: string;
  channelId: string;
  channel: string;
  /** Stimulation score 0–100, one decimal. */
  score: number;
};

/** One of the 12 measurements, in taxonomy order. */
export type Feature = {
  key: string;
  /** Raw value; null when it couldn't be measured. */
  value: number | null;
  /** Percentile 0–100 in the dataset, one decimal; null when `value` is. */
  percentile: number | null;
};

export type VideoDetail = VideoSummary & {
  /** False for a video checked live from a channel we don't have: no channel page to link to. */
  channelInDataset: boolean;
  features: Feature[];
};

export type ChannelSummary = {
  id: string;
  name: string;
  /** Mean stimulation score of the channel's videos, 0–100, one decimal. */
  score: number;
  videoCount: number;
};

/** One of a channel's videos, with its scores (as in `VideoDetail`). */
export type ChannelVideo = {
  id: string;
  title: string;
  /** YYYY-MM-DD */
  publishedAt: string;
  /** Stimulation score 0–100, one decimal. */
  score: number;
  features: Feature[];
};

export type ChannelDetail = {
  id: string;
  name: string;
  videoCount: number;
  /** Mean stimulation score of the channel's videos, 0–100, one decimal. */
  score: number;
  /**
   * The 12 measurements: `value` is the mean raw value and `percentile` the mean of the videos'
   * percentiles, over the videos that have one; null if none has.
   */
  features: Feature[];
  /** Oldest first. */
  videos: ChannelVideo[];
};

export type ListResponse<T> = {
  items: T[];
  total: number;
};

export type Sort = "score_desc" | "score_asc";

/** Where a live analysis is: waiting, one of its three steps, or finished. */
export type AnalysisStatus = "queued" | "lookup" | "download" | "measure" | "done" | "failed";

/** Why a live analysis failed. */
export type AnalysisErrorCode = "unavailable" | "not_for_kids" | "too_short" | "live" | "failed";

/** A live analysis of a video that isn't in the dataset. */
export type Analysis = {
  status: AnalysisStatus;
  /** Videos ahead of this one, while queued. */
  queuePosition: number | null;
  /** Estimated progress 0–1; 1 only when done. */
  progress: number;
  /** Estimated seconds left; null while queued, done or failed. */
  remainingS: number | null;
  /** The current step is taking much longer than usual. */
  error: AnalysisErrorCode | null;
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export type Params = Record<string, string | number>;

export type Method = "GET" | "POST";

async function request<T>(method: Method, path: string, params: Params = {}): Promise<T> {
  if (process.env.NEXT_PUBLIC_API_MOCK === "1") {
    const { mockRequest } = await import("./mock");
    return mockRequest(method, path, params) as Promise<T>;
  }
  const query = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)]),
  ).toString();
  const url = `${API_BASE}${path}${query ? `?${query}` : ""}`;
  // No body and no custom headers, so a POST needs no CORS preflight.
  const res = await fetch(url, { method, headers: { Accept: "application/json" } });
  if (!res.ok) {
    throw new ApiError(res.status, `${method} ${path} failed with ${res.status}`);
  }
  return (await res.json()) as T;
}

function get<T>(path: string, params: Params = {}): Promise<T> {
  return request("GET", path, params);
}

export function getMeta(): Promise<Meta> {
  return get<Meta>("/api/meta");
}

export function getVideos(params: {
  sort: Sort;
  limit: number;
}): Promise<ListResponse<VideoSummary>> {
  return get("/api/videos", params);
}

export function getChannels(params: {
  sort: Sort;
  limit: number;
  minVideos: number;
}): Promise<ListResponse<ChannelSummary>> {
  return get("/api/channels", params);
}

/**
 * One video in the dataset, or one analyzed live. Any other video rejects with an `ApiError`
 * with status 404.
 */
export function getVideo(id: string): Promise<VideoDetail> {
  return get(`/api/videos/${encodeURIComponent(id)}`);
}

/** One channel in the dataset. Any other rejects with an `ApiError` with status 404. */
export function getChannel(id: string): Promise<ChannelDetail> {
  return get(`/api/channels/${encodeURIComponent(id)}`);
}

/**
 * Starts the live analysis of a video, or joins it if it is running or done. Rejects with an
 * `ApiError` with status 429 (too many new analyses from this visitor) or 503 (queue full).
 */
export function startAnalysis(id: string): Promise<Analysis> {
  return request("POST", `/api/analyses/${encodeURIComponent(id)}`);
}

/** A live analysis' progress. Rejects with an `ApiError` with status 404 if it was never started. */
export function getAnalysis(id: string): Promise<Analysis> {
  return get(`/api/analyses/${encodeURIComponent(id)}`);
}
