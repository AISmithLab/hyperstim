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

function barColor(score: number): string {
  if (score >= 67) return "bg-scale-high";
  if (score >= 34) return "bg-scale-mid";
  return "bg-scale-low";
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
          Most stimulating
        </h2>
        <div role="group" aria-label="Show ranking of" className="flex gap-2">
          {(Object.keys(VIEWS) as View[]).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={view === v}
              onClick={() => setView(v)}
              className="min-h-11 rounded-full border-2 border-navy/20 bg-white px-5 font-semibold text-navy hover:border-navy/50 aria-pressed:border-sunny aria-pressed:bg-sunny"
            >
              {VIEWS[v].chip}
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
            <col className="w-14" />
            <col />
            <col className="w-20 sm:w-32" />
          </colgroup>
          <thead>
            <tr className="border-b border-navy/15 text-left text-sm text-ink">
              <th scope="col" className="py-2 pr-2 font-semibold">
                <span aria-hidden="true">#</span>
                <span className="sr-only">Rank</span>
              </th>
              <th scope="col" className="py-2 pr-2 font-semibold">
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
            {state.status === "loading" ? <SkeletonRows /> : <RankRows rows={state.data} />}
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

/** Marks the skipped middle of the ranking. Screen readers get the gap from the rank numbers. */
function GapRow() {
  return (
    <tr aria-hidden="true" className="border-b border-navy/10">
      <td colSpan={3} className="py-1 pl-1 text-lg leading-none font-bold text-ink">
        …
      </td>
    </tr>
  );
}

function RankRows({ rows }: { rows: Row[] }) {
  return rows.map((row, i) => {
    const gap = i > 0 && row.rank > rows[i - 1].rank + 1;
    return [gap && <GapRow key={`gap-${row.key}`} />, <RankRow key={row.key} row={row} />];
  });
}

function SkeletonRows() {
  const bar = "block animate-pulse rounded bg-gray-200";
  const row = (i: number) => (
    <tr key={i} className={ROW}>
      <td className="pr-2">
        <span className={`${bar} h-4 w-4`} />
      </td>
      <td className="pr-2">
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

function RankRow({ row }: { row: Row }) {
  const warn = row.rank <= END;
  const score = Math.round(row.score);
  return (
    <tr className={`relative ${ROW}`}>
      {/* Ranks 1–3 get the warning-triangle art behind the number once it arrives (plan 002). */}
      <td
        className={`pr-2 pl-1 align-middle text-sm font-bold tabular-nums sm:text-base ${warn ? "text-navy" : "text-ink"}`}
      >
        {row.rank.toLocaleString("en-US")}
      </td>
      <td className="pr-2 align-middle">
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
        <span className="flex items-center gap-2">
          <span className="w-7 text-right font-bold text-navy tabular-nums">{score}</span>
          <span aria-hidden="true" className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
            <span
              className={`block h-full rounded-full ${barColor(score)}`}
              style={{ width: `${score}%` }}
            />
          </span>
        </span>
      </td>
    </tr>
  );
}
