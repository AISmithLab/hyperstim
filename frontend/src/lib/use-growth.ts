"use client";

import { useEffect, useState } from "react";
import { getMeta, getVideos, type Meta } from "./api";
import { pastWeek } from "./search-filters";

/** How often an open page asks whether videos were added, while it's visible. */
export const POLL_MS = 60_000;

export type Growth = {
  videos: number;
  channels: number;
  /** Videos added in the past week: the last 7 days, today included, in the visitor's time zone. */
  pastWeek: number;
  /** The rankings' search for those videos, e.g. `added:>2026-10-19`. */
  pastWeekQuery: string;
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
  const [first, setFirst] = useState<(Meta & { week: number; query: string }) | "loading" | "failed">("loading");
  const [latest, setLatest] = useState<{ videos: number; channels: number } | null>(null);

  useEffect(() => {
    let alive = true;
    // The pill counts what its link lists: the rankings' total for the same filter.
    const week = pastWeek();
    Promise.all([getMeta(), getVideos({ sort: "score", order: "desc", limit: 1, addedFrom: week.from })]).then(
      ([meta, added]) => {
        if (!alive) return;
        setFirst({ ...meta, week: added.total, query: week.query });
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
    pastWeek: first.week + (latest.videos - first.videoCount),
    pastWeekQuery: first.query,
    from: {
      videos: Math.max(0, first.videoCount - first.week),
      channels: Math.min(first.channelCount7DaysAgo, first.channelCount),
      pastWeek: 0,
    },
  };
}
