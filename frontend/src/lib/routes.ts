/** Link to a channel's page. The page itself comes in a later plan. */
export function channelHref(channelId: string): string {
  return `/channel?id=${encodeURIComponent(channelId)}`;
}
