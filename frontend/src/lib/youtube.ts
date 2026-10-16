export type ParseResult =
  | { ok: true; id: string }
  | { ok: false; reason: "empty" | "invalid" };

const ID = /^[A-Za-z0-9_-]{11}$/;
const CHANNEL_ID = /^UC[A-Za-z0-9_-]{22}$/;

/** A YouTube channel link: `/channel/UC…`, `/@handle`, `/c/…` or `/user/…`. */
export function isChannelLink(input: string): boolean {
  let url: URL;
  const text = input.trim();
  try {
    url = new URL(/^https?:\/\//i.test(text) ? text : `https://${text}`);
  } catch {
    return false;
  }
  const host = url.hostname.toLowerCase().replace(/^www\./, "");
  if (!HOSTS.has(host) || host === "youtu.be") return false;
  const [first, second] = url.pathname.split("/").filter(Boolean);
  if (first === "channel") return CHANNEL_ID.test(second ?? "");
  if (first === "c" || first === "user") return Boolean(second);
  return /^@./.test(first ?? "");
}

/** A bare 11-character video ID. */
export function isVideoId(text: string): boolean {
  return ID.test(text);
}

/** A channel ID ("UC" and 22 characters). */
export function isChannelId(text: string): boolean {
  return CHANNEL_ID.test(text);
}
const HOSTS = new Set([
  "youtube.com",
  "m.youtube.com",
  "music.youtube.com",
  "youtube-nocookie.com",
  "youtu.be",
]);
const PATH_PREFIXES = ["shorts", "embed", "live", "v"];

/** Extracts the 11-character video ID from a YouTube link or a bare ID. */
export function parseVideoInput(input: string): ParseResult {
  const text = input.trim();
  if (!text) return { ok: false, reason: "empty" };
  if (ID.test(text)) return { ok: true, id: text };

  let url: URL;
  try {
    url = new URL(/^https?:\/\//i.test(text) ? text : `https://${text}`);
  } catch {
    return { ok: false, reason: "invalid" };
  }
  const host = url.hostname.toLowerCase().replace(/^www\./, "");
  if (!HOSTS.has(host)) return { ok: false, reason: "invalid" };

  const segments = url.pathname.split("/").filter(Boolean);
  let candidate: string | null | undefined;
  if (host === "youtu.be") {
    candidate = segments[0];
  } else if (segments[0] === "watch") {
    candidate = url.searchParams.get("v");
  } else if (PATH_PREFIXES.includes(segments[0])) {
    candidate = segments[1];
  }
  return candidate && ID.test(candidate)
    ? { ok: true, id: candidate }
    : { ok: false, reason: "invalid" };
}

/**
 * A video's thumbnail on YouTube's image server: `hq` is 480×360 (4:3, letterboxed), `mq`
 * 320×180 (16:9).
 */
export function thumbnailUrl(id: string, size: "hq" | "mq" = "hq"): string {
  return `https://i.ytimg.com/vi/${encodeURIComponent(id)}/${size}default.jpg`;
}
