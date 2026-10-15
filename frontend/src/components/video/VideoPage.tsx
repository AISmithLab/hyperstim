"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import YouTubePlayer from "@/components/YouTubePlayer";
import { ApiError, getVideo, type VideoDetail } from "@/lib/api";
import { asset } from "@/lib/asset";
import { useApi } from "@/lib/use-api";
import { channelHref } from "@/lib/routes";
import { parseVideoInput } from "@/lib/youtube";
import LiveAnalysis from "./LiveAnalysis";
import { CheckAnother, CONTAINER, Message, OUTLINED_BUTTON } from "./parts";
import ScorePanel, { ScorePanelSkeleton } from "./ScorePanel";

// Video metadata on 2/3 of the width, the preview on 1/3.
const HEADER = "grid grid-cols-[2fr_1fr] items-start gap-4 sm:gap-6";
// Room above the score panel for the kid peeking over its top edge.
const PANEL_GAP = "mt-28 sm:mt-20 lg:mt-16 xl:mt-10";

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

      <ScorePanel
        score={video.score}
        features={video.features}
        subject="video"
        className={PANEL_GAP}
        kid={<PanelKid />}
        scoreInfo={
          <p>
            Score 0–100: where this video’s production sits among the videos in our dataset. We measure
            production style only.
          </p>
        }
      />
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
      <ScorePanelSkeleton className={PANEL_GAP} />
    </div>
  );
}
