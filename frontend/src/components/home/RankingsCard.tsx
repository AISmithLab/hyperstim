"use client";

import Link from "next/link";
import { useState } from "react";
import InfoTip from "@/components/InfoTip";
import { getChannels, getVideos, type ListResponse } from "@/lib/api";
import { asset } from "@/lib/asset";
import { useApi } from "@/lib/use-api";

/** Rows shown from each end of the ranking. */
const END = 3;

type Row = {
  key: string;
  rank: number;
  name: string;
  detail: string;
  score: number;
  href?: string;
};

/**
 * Joins the most and least stimulating items into one ranking. Ranks of the least stimulating
 * count back from `total`; items already in the top are dropped when the dataset is small.
 */
export function joinEnds<T>(
  top: ListResponse<T>,
  bottom: ListResponse<T>,
  toRow: (item: T, rank: number) => Row,
): Row[] {
  const rows = top.items.map((item, i) => toRow(item, i + 1));
  const tail = bottom.items
    .map((item, i) => toRow(item, bottom.total - i))
    .filter((row) => row.rank > rows.length)
    .reverse();
  return [...rows, ...tail];
}

async function loadVideos(): Promise<Row[]> {
  const [top, bottom] = await Promise.all([
    getVideos({ sort: "score_desc", limit: END }),
    getVideos({ sort: "score_asc", limit: END }),
  ]);
  return joinEnds(top, bottom, (v, rank) => ({
    key: v.id,
    rank,
    name: v.title,
    detail: v.channel,
    score: v.score,
    href: `/video?id=${encodeURIComponent(v.id)}`,
  }));
}

async function loadChannels(): Promise<Row[]> {
  const [top, bottom] = await Promise.all([
    getChannels({ sort: "score_desc", limit: END, minVideos: 5 }),
    getChannels({ sort: "score_asc", limit: END, minVideos: 5 }),
  ]);
  return joinEnds(top, bottom, (c, rank) => ({
    key: c.name,
    rank,
    name: c.name,
    detail: `${c.videoCount} videos`,
    score: c.score,
  }));
}

type View = "videos" | "channels";

const VIEWS: Record<View, { chip: string; column: string; caption: string }> = {
  videos: {
    chip: "Videos",
    column: "Video",
    caption: "The 3 most and 3 least stimulating videos",
  },
  channels: {
    chip: "Channels",
    column: "Channel",
    caption: "The 3 most and 3 least stimulating channels",
  },
};

/** Colour of the score meter by filled segments, cool for low scores and warm for high ones. */
const METER_COLORS = ["bg-sky-blue", "bg-leaf", "bg-scale-low", "bg-scale-mid", "bg-scale-high"];
const SEGMENTS = METER_COLORS.length;

/**
 * Filled segments of the score meter: one per 20 points, at least one so a score of 0 still
 * shows the meter's colour. The number next to it is the exact score.
 */
export function filledSegments(score: number): number {
  return Math.max(1, Math.ceil((score * SEGMENTS) / 100));
}

// Every row has room for a two-line name plus the small second line, so switching
// between videos and channels never changes the card's height.
const ROW = "h-20 border-b border-navy/10 last:border-0";

export default function RankingsCard() {
  const [view, setView] = useState<View>("videos");
  // Both lists load up front so switching views is instant.
  const videos = useApi(loadVideos);
  const channels = useApi(loadChannels);
  const state = view === "videos" ? videos : channels;

  return (
    <section
      aria-labelledby="rankings-heading"
      className="relative rounded-[2rem] border border-navy/15 bg-white px-4 py-8 sm:px-8"
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- decorative */}
      <img
        src={asset("/images/flower_2.webp")}
        alt=""
        aria-hidden="true"
        width={300}
        height={150}
        className="pointer-events-none absolute -top-14 right-8 hidden h-auto w-36 md:block"
      />

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
        <h2 id="rankings-heading" className="font-hand text-2xl font-semibold text-navy sm:text-3xl">
          Stimulation rankings
        </h2>
        {/* Segmented control: each button is a 44px touch target; the visible pill sits inside it. */}
        <div
          role="group"
          aria-label="Show ranking of"
          className="flex rounded-full border border-navy/15 bg-white px-0.5"
        >
          {(Object.keys(VIEWS) as View[]).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={view === v}
              onClick={() => setView(v)}
              className="group flex min-h-11 items-center rounded-full text-sm font-semibold text-navy"
            >
              <span className="rounded-full px-3 py-1.5 group-hover:bg-sky group-aria-pressed:bg-sunny">
                {VIEWS[v].chip}
              </span>
            </button>
          ))}
        </div>
      </div>

      <p role="status" className="sr-only">
        {state.status === "loading" ? "Loading rankings…" : ""}
      </p>

      {state.status === "error" ? (
        <div className="mt-6 rounded-2xl bg-sky p-6 text-center">
          <p>We couldn’t load the rankings.</p>
          <button
            type="button"
            onClick={state.retry}
            className="mt-3 min-h-11 rounded-full border-2 border-navy px-5 font-semibold text-navy hover:bg-white"
          >
            Try again
          </button>
        </div>
      ) : state.status === "success" && state.data.length === 0 ? (
        <p className="mt-6 rounded-2xl bg-sky p-6 text-center">No rankings yet.</p>
      ) : (
        <table
          className="mt-6 w-full table-fixed border-collapse"
          aria-busy={state.status === "loading"}
        >
          <caption className="sr-only">{VIEWS[view].caption}</caption>
          <colgroup>
            <col className="w-10 sm:w-12" />
            <col />
            <col className="w-20 sm:w-28" />
          </colgroup>
          <thead>
            <tr className="border-b border-navy/15 text-left text-sm text-ink">
              <th scope="col" className="py-2 pr-4 text-right font-semibold sm:pr-5">
                <span aria-hidden="true">#</span>
                <span className="sr-only">Rank</span>
              </th>
              <th scope="col" className="py-2 pr-4 sm:pr-6 font-semibold">
                {VIEWS[view].column}
              </th>
              <th scope="col" className="py-2 font-semibold">
                <span className="flex items-center gap-1">
                  Score
                  <InfoTip id="score-info" label="About the score" className="-my-3">
                    <p>Score 0–100: how intense the production is compared with the rest of our dataset.</p>
                    <p className="mt-2">A channel’s score is the average of its videos.</p>
                  </InfoTip>
                </span>
              </th>
            </tr>
          </thead>
          <tbody>
            {state.status === "loading" ? (
              <SkeletonRows />
            ) : (
              <RankRows rows={state.data} />
            )}
          </tbody>
        </table>
      )}

      <Link
        href="/rankings"
        className="mt-6 inline-flex min-h-11 items-center font-bold text-navy underline decoration-2 underline-offset-4 hover:decoration-sunny"
      >
        See full rankings&nbsp;<span aria-hidden="true">→</span>
      </Link>
    </section>
  );
}

/** Marks where the least stimulating end of the ranking starts. */
function GapRow() {
  return (
    <tr className="h-9 border-b border-navy/10">
      <td colSpan={3} className="text-center text-sm text-ink/80">
        <span aria-hidden="true">↓</span> Least stimulating
      </td>
    </tr>
  );
}

/**
 * Rows after a gap in the ranking count back from the end (−3, −2, −1); without a gap
 * (small dataset), every row shows its plain rank.
 */
function RankRows({ rows }: { rows: Row[] }) {
  const gapAt = rows.findIndex((row, i) => i > 0 && row.rank > rows[i - 1].rank + 1);
  const last = rows.at(-1)?.rank ?? 0;
  return rows.map((row, i) => {
    const fromEnd = gapAt > 0 && i >= gapAt ? last - row.rank + 1 : undefined;
    return [
      i === gapAt && <GapRow key="gap" />,
      <RankRow key={row.key} row={row} fromEnd={fromEnd} />,
    ];
  });
}

/** "3rd", for the screen-reader text of ranks counted from the end. */
function ordinal(n: number): string {
  return n === 1 ? "" : n === 2 ? "2nd " : n === 3 ? "3rd " : `${n}th `;
}

function SkeletonRows() {
  const bar = "block animate-pulse rounded bg-gray-200";
  const row = (i: number) => (
    <tr key={i} className={ROW}>
      <td className="pr-4 sm:pr-5">
        <span className={`${bar} ml-auto h-4 w-4`} />
      </td>
      <td className="pr-4 sm:pr-6">
        <span className={`${bar} h-4 w-4/5`} />
        <span className={`${bar} mt-2 h-3 w-2/5`} />
      </td>
      <td>
        <span className={`${bar} h-4 w-16`} />
      </td>
    </tr>
  );
  return (
    <>
      {[0, 1, 2].map(row)}
      <GapRow />
      {[3, 4, 5].map(row)}
    </>
  );
}

function RankRow({ row, fromEnd }: { row: Row; fromEnd?: number }) {
  const warn = row.rank <= END;
  const score = Math.round(row.score);
  const filled = filledSegments(score);
  return (
    <tr className={`relative ${ROW}`}>
      {/* Ranks 1–3 may get warning-triangle art behind the number later (plan 002). */}
      <td
        className={`pr-4 text-right align-middle text-sm font-bold tabular-nums sm:pr-5 sm:text-base ${warn ? "text-navy" : "text-ink"}`}
      >
        {fromEnd ? (
          <>
            <span aria-hidden="true">−{fromEnd}</span>
            <span className="sr-only">{`${ordinal(fromEnd)}least stimulating`}</span>
          </>
        ) : (
          row.rank.toLocaleString("en-US")
        )}
      </td>
      <td className="pr-4 align-middle sm:pr-6">
        {row.href ? (
          <Link
            href={row.href}
            className="line-clamp-2 font-semibold text-navy after:absolute after:inset-0 hover:underline"
          >
            {row.name}
          </Link>
        ) : (
          <span className="line-clamp-2 font-semibold text-navy">{row.name}</span>
        )}
        <span className="mt-0.5 block truncate text-sm">{row.detail}</span>
      </td>
      <td className="align-middle">
        {/* Number above the meter on phones, beside it from sm up. */}
        <span className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
          <span className="font-bold text-navy tabular-nums sm:w-7 sm:text-right">{score}</span>
          <span aria-hidden="true" data-filled={filled} className="flex flex-1 gap-1">
            {Array.from({ length: SEGMENTS }, (_, i) => (
              <span
                key={i}
                className={`h-2.5 flex-1 rounded-[3px] ${i < filled ? METER_COLORS[filled - 1] : "bg-navy/10"}`}
              />
            ))}
          </span>
        </span>
      </td>
    </tr>
  );
}
