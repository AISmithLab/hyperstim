"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, type ReactNode } from "react";
import InfoTip from "@/components/InfoTip";
import YouTubePlayer from "@/components/YouTubePlayer";
import { ApiError, getMeta, getVideo, type VideoDetail } from "@/lib/api";
import { asset } from "@/lib/asset";
import { useApi } from "@/lib/use-api";
import { channelHref } from "@/lib/routes";
import { parseVideoInput } from "@/lib/youtube";
import Measurements from "./Measurements";
import ScoreGauge from "./ScoreGauge";

const CONTAINER = "mx-auto max-w-6xl px-4 pt-6 sm:px-6 lg:px-8";
const SECTION_CARD = "rounded-[2rem] border border-navy/15 bg-white px-4 py-6 sm:px-8";
const MESSAGE_BOX = "rounded-2xl bg-sky p-6 text-center";
const TEXT_LINK =
  "inline-flex min-h-11 items-center font-bold text-navy underline decoration-2 underline-offset-4 hover:decoration-sunny";
// Video metadata on 2/3 of the width, the preview on 1/3.
const HEADER = "grid grid-cols-[2fr_1fr] items-start gap-4 sm:gap-6";
// Room above the score panel for the kid peeking over its top edge.
const PANEL_GAP = "mt-28 sm:mt-20 lg:mt-16 xl:mt-10";
// Gauge column beside the measurements from lg; wider, with a wider gap, from xl.
const PANEL_GRID = "grid lg:grid-cols-[13rem_1fr] lg:gap-x-8 xl:grid-cols-[17rem_1fr] xl:gap-x-12";
// The gauge fills its column from lg and is vertically centred against the measurements.
const GAUGE = "mx-auto w-full max-w-48 lg:max-w-none lg:self-center";

/** `/video?id=…`: reads the ID on the client, since a static export can't pre-render it. */
export default function VideoPage() {
  const raw = useSearchParams().get("id") ?? "";
  const parsed = parseVideoInput(raw);
  // A bare ID only: links here always carry one.
  if (!parsed.ok || parsed.id !== raw) return <InvalidId />;
  return <VideoDetails key={raw} id={raw} />;
}

function VideoDetails({ id }: { id: string }) {
  const load = useCallback(() => getVideo(id), [id]);
  const video = useApi(load);
  const meta = useApi(getMeta);
  const count = meta.status === "success" ? meta.data.videoCount : undefined;

  useEffect(() => {
    if (video.status === "success") document.title = `${video.data.title} - HyperStim?`;
  }, [video]);

  if (video.status === "loading") return <Loading />;
  if (video.status === "error") {
    return video.error instanceof ApiError && video.error.status === 404 ? (
      <NotChecked id={id} count={count} />
    ) : (
      <Message>
        <p>We couldn’t load this video.</p>
        <button
          type="button"
          onClick={video.retry}
          className="mt-3 min-h-11 rounded-full border-2 border-navy px-5 font-semibold text-navy hover:bg-white"
        >
          Try again
        </button>
      </Message>
    );
  }
  return <Result video={video.data} />;
}

function Result({ video }: { video: VideoDetail }) {
  return (
    <div className={CONTAINER}>
      <div className={HEADER}>
        <div className="min-w-0">
          <h1 className="line-clamp-2 font-hand text-[1.375rem] leading-tight font-semibold text-navy sm:text-2xl lg:text-[1.75rem]">
            {video.title}
          </h1>
          <p className="mt-1 truncate">
            <Link href={channelHref(video.channelId)} className="font-bold text-navy hover:underline">
              {video.channel}
            </Link>
          </p>
        </div>
        {/* The preview plays in place on click; the embedded player links on to YouTube. */}
        <YouTubePlayer id={video.id} title={video.title} />
      </div>

      <section aria-labelledby="score-heading" className={`relative ${PANEL_GAP} ${SECTION_CARD}`}>
        <PanelKid />
        <h2 id="score-heading" className="sr-only">
          Stimulation score
        </h2>
        <div className={PANEL_GRID}>
          <div className={GAUGE}>
            <ScoreGauge score={video.score}>
              <InfoTip id="score-info" label="About the stimulation score">
                <p>
                  Score 0–100: where this video’s production sits among the videos in our dataset, not
                  whether it is good or bad.
                </p>
              </InfoTip>
            </ScoreGauge>
          </div>
          <div className="mt-6 border-t border-navy/10 pt-4 lg:mt-0 lg:border-t-0 lg:pt-0">
            <Measurements features={video.features} />
          </div>
        </div>
      </section>
    </div>
  );
}

/** The kid peeking over the panel's top edge, hands on the border line, looking toward the measurements. */
function PanelKid() {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- static export, images pre-converted
    <img
      src={asset("/images/kid_3.webp")}
      alt=""
      aria-hidden="true"
      width={416}
      height={277}
      data-kid=""
      // The art's table edge is 92.1% down the image; it sits on the border.
      className="pointer-events-none absolute top-0 left-2 h-auto w-40 -translate-y-[92.1%] sm:left-6 sm:w-44 lg:left-[5.5rem] lg:w-52 xl:left-[10.5rem]"
    />
  );
}

function WatchOnYouTube({ id }: { id: string }) {
  return (
    <a
      href={`https://www.youtube.com/watch?v=${encodeURIComponent(id)}`}
      target="_blank"
      rel="noopener noreferrer"
      className={TEXT_LINK}
    >
      {/* One span, so the text and arrow wrap like plain text in a narrow column. */}
      <span>
        Watch on YouTube&nbsp;<span aria-hidden="true">↗</span>
        <span className="sr-only"> (opens in a new tab)</span>
      </span>
    </a>
  );
}

function CheckAnother() {
  return (
    <Link href="/" className={TEXT_LINK}>
      Check another video&nbsp;<span aria-hidden="true">→</span>
    </Link>
  );
}

/** States without a result: a visually hidden H1 and a message box. */
function Message({ children }: { children: ReactNode }) {
  return (
    <div className={CONTAINER}>
      <h1 className="sr-only">Video details</h1>
      <div className={`mx-auto max-w-2xl ${MESSAGE_BOX}`}>{children}</div>
    </div>
  );
}

function InvalidId() {
  return (
    <Message>
      <p>That doesn’t look like a YouTube video ID.</p>
      <div className="mt-2">
        <CheckAnother />
      </div>
    </Message>
  );
}

function NotChecked({ id, count }: { id: string; count?: number }) {
  return (
    <div className={CONTAINER}>
      {/* eslint-disable-next-line @next/next/no-img-element -- static export, images pre-converted */}
      <img
        src={asset("/images/kid_2.webp")}
        alt=""
        aria-hidden="true"
        width={560}
        height={280}
        className="mx-auto h-auto w-[280px]"
      />
      <div className={`mx-auto max-w-2xl ${MESSAGE_BOX}`}>
        <h1 className="font-hand text-2xl font-semibold text-navy sm:text-3xl">
          We haven’t checked this video yet
        </h1>
        <p className="mt-2">
          It isn’t one of the {count === undefined ? "" : `${count.toLocaleString("en-US")} `}videos in our
          dataset. Checking new videos is coming soon.
        </p>
        <div className="mt-2 flex flex-wrap justify-center gap-x-6">
          <CheckAnother />
          <WatchOnYouTube id={id} />
        </div>
      </div>
    </div>
  );
}

/** Skeleton of the title block and score panel; also the Suspense fallback. */
export function Loading() {
  const bar = "block animate-pulse rounded bg-gray-200";
  return (
    <div className={CONTAINER} aria-busy="true">
      <h1 className="sr-only">Video details</h1>
      <p role="status" className="sr-only">
        Loading video…
      </p>
      <div className={HEADER}>
        <div className="min-w-0">
          <span className={`${bar} h-7 w-4/5`} />
          <span className={`${bar} mt-2 h-5 w-1/3`} />
        </div>
        <div className="aspect-video w-full animate-pulse rounded-2xl bg-gray-200" />
      </div>
      <div className={`${PANEL_GAP} ${SECTION_CARD}`}>
        <div className={PANEL_GRID}>
          <div className={GAUGE}>
            <svg aria-hidden="true" viewBox="0 0 240 132" className="w-full">
              <path d="M 24 118 A 96 96 0 0 1 216 118" fill="none" strokeWidth={26} className="stroke-gray-200" />
            </svg>
            <span className={`${bar} mx-auto mt-6 h-10 w-28`} />
          </div>
          <div className="mt-6 grid gap-x-6 border-t border-navy/10 pt-4 md:grid-cols-2 lg:mt-0 lg:border-t-0 lg:pt-0">
            {[6, 6].map((rows, col) => (
              <div key={col}>
                {Array.from({ length: rows }, (_, i) => (
                  <div key={i} className="flex h-11 items-center justify-between gap-4 border-b border-navy/10 last:border-0">
                    <span className={`${bar} h-4 w-2/5`} />
                    <span className={`${bar} h-4 w-24`} />
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
