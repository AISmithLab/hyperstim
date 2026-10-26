"use client";

import { useEffect, useState } from "react";
import { getMeta, type Meta } from "./api";

/** How often an open page asks whether videos were added, while it's visible. */
export const POLL_MS = 60_000;

export type Growth = {
  videos: number;
  channels: number;
  /** Videos added in the past week (the last 7 × 24 hours). */
  pastWeek: number;
  /** Where the first count-up starts: the counts a week ago. */
  from: { videos: number; channels: number; pastWeek: number };
};

/** "loading" until the first answer, "failed" if it can't be had. */
export type GrowthState = Growth | "loading" | "failed";

/**
 * The dataset's size, growing while the page is open (plan 013). It asks the API once, then every
 * minute while the tab is visible. The numbers only ever go up during a page's life: a video taken
 * out, or the past week moving on, shows at the next page load.
 */
export function useGrowth(): GrowthState {
  const [first, setFirst] = useState<Meta | "loading" | "failed">("loading");
  const [latest, setLatest] = useState<{ videos: number; channels: number } | null>(null);

  useEffect(() => {
    let alive = true;
    getMeta().then(
      (meta) => {
        if (!alive) return;
        setFirst(meta);
        setLatest({ videos: meta.videoCount, channels: meta.channelCount });
      },
      () => alive && setFirst("failed"), // the page shows its text without numbers
    );
    const timer = setInterval(() => {
      if (document.visibilityState !== "visible") return;
      getMeta().then(
        (meta) =>
          alive &&
          setLatest((shown) =>
            shown
              ? { videos: Math.max(shown.videos, meta.videoCount), channels: Math.max(shown.channels, meta.channelCount) }
              : shown,
          ),
        () => {}, // try again in a minute
      );
    }, POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  if (first === "loading" || first === "failed") return first;
  if (!latest) return "loading";
  return {
    videos: latest.videos,
    channels: latest.channels,
    pastWeek: first.addedLast7Days + (latest.videos - first.videoCount),
    from: {
      videos: Math.max(0, first.videoCount - first.addedLast7Days),
      channels: Math.min(first.channelCount7DaysAgo, first.channelCount),
      pastWeek: 0,
    },
  };
}
