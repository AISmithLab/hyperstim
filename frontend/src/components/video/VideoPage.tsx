"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import InfoTip from "@/components/InfoTip";
import YouTubePlayer from "@/components/YouTubePlayer";
import { ApiError, getVideo, type VideoDetail } from "@/lib/api";
import { asset } from "@/lib/asset";
import { useApi } from "@/lib/use-api";
import { channelHref } from "@/lib/routes";
import { parseVideoInput } from "@/lib/youtube";
import LiveAnalysis from "./LiveAnalysis";
import Measurements from "./Measurements";
import { CheckAnother, CONTAINER, Message, OUTLINED_BUTTON } from "./parts";
import ScoreGauge from "./ScoreGauge";

const SECTION_CARD = "rounded-[2rem] border border-navy/15 bg-white px-4 py-6 sm:px-8";
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
  // Live analysis step changes, read out by screen readers. Outside the states below, so
  // it stays on the page while they change.
  const [announcement, setAnnouncement] = useState("");

  useEffect(() => {
    if (video.status === "success") document.title = `${video.data.title} - HyperStim?`;
  }, [video]);

  return (
    <>
      <VideoState id={id} video={video} announce={setAnnouncement} />
      <p aria-live="polite" className="sr-only">
        {announcement}
      </p>
    </>
  );
}

function VideoState({
  id,
  video,
  announce,
}: {
  id: string;
  video: ReturnType<typeof useApi<VideoDetail>>;
  announce: (text: string) => void;
}) {
  if (video.status === "loading") return <Loading />;
  if (video.status === "error") {
    // Not in the dataset: analyze it live, then load the result.
    return video.error instanceof ApiError && video.error.status === 404 ? (
      <LiveAnalysis id={id} onDone={video.retry} announce={announce} />
    ) : (
      <Message>
        <p>We couldn’t load this video.</p>
        <button type="button" onClick={video.retry} className={`mt-3 ${OUTLINED_BUTTON}`}>
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
          <p className="mt-1 truncate font-bold text-navy">
            {/* A live-checked video's channel may have no page here. */}
            {video.channelInDataset ? (
              <Link href={channelHref(video.channelId)} className="hover:underline">
                {video.channel}
              </Link>
            ) : (
              video.channel
            )}
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
