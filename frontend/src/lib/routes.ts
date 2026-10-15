/** Link to a channel's page. */
export function channelHref(channelId: string): string {
  return `/channel?id=${encodeURIComponent(channelId)}`;
}

/** Link to a video's page. */
export function videoHref(videoId: string): string {
  return `/video?id=${encodeURIComponent(videoId)}`;
}
