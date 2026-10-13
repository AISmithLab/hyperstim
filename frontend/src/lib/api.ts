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
  channel: string;
  /** Stimulation score 0–100, one decimal. */
  score: number;
};

export type ChannelSummary = {
  name: string;
  /** Mean stimulation score of the channel's videos, 0–100, one decimal. */
  score: number;
  videoCount: number;
};

export type ListResponse<T> = {
  items: T[];
  total: number;
};

export type Sort = "score_desc" | "score_asc";

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

async function get<T>(path: string, params: Params = {}): Promise<T> {
  if (process.env.NEXT_PUBLIC_API_MOCK === "1") {
    const { mockGet } = await import("./mock");
    return mockGet(path, params) as Promise<T>;
  }
  const query = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)]),
  ).toString();
  const url = `${API_BASE}${path}${query ? `?${query}` : ""}`;
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    throw new ApiError(res.status, `GET ${path} failed with ${res.status}`);
  }
  return (await res.json()) as T;
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
