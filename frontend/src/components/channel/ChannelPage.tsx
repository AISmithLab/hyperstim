"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect } from "react";
import { CheckAnother, CONTAINER, KidMessage, Message, OUTLINED_BUTTON, TEXT_LINK } from "@/components/video/parts";
import ScorePanel, { ScorePanelSkeleton } from "@/components/video/ScorePanel";
import { ApiError, getChannel, type ChannelDetail } from "@/lib/api";
import { asset } from "@/lib/asset";
import { useApi } from "@/lib/use-api";
import { metaLine } from "./chart";
import OverYears, { SECTION_CARD } from "./OverYears";

const CHANNEL_ID = /^UC[A-Za-z0-9_-]{22}$/;
const HEADING = "Channel details";
// Name and meta line on 2/3 of the width; the kid's head rises into the right third.
const HEADER = "grid grid-cols-[2fr_1fr] items-start gap-4 sm:gap-6";

/** `/channel?id=…`: reads the ID on the client, since a static export can't pre-render it. */
export default function ChannelPage() {
  const id = useSearchParams().get("id") ?? "";
  if (!CHANNEL_ID.test(id)) {
    return (
      <Message heading={HEADING}>
        <p>That doesn’t look like a channel link.</p>
        <div className="mt-2">
          <CheckAnother label="Check a video" />
        </div>
      </Message>
    );
  }
  return <ChannelDetails key={id} id={id} />;
}

function ChannelDetails({ id }: { id: string }) {
  const load = useCallback(() => getChannel(id), [id]);
  const channel = useApi(load);

  useEffect(() => {
    if (channel.status === "success") document.title = `${channel.data.name} - HyperStim?`;
  }, [channel]);

  if (channel.status === "loading") return <Loading />;
  if (channel.status === "error") {
    return channel.error instanceof ApiError && channel.error.status === 404 ? (
      <KidMessage heading={HEADING}>
        <p>This channel isn’t in our dataset.</p>
        <div className="mt-2">
          <CheckAnother label="Check a video" />
        </div>
      </KidMessage>
    ) : (
      <Message heading={HEADING}>
        <p>We couldn’t load this channel.</p>
        <button type="button" onClick={channel.retry} className={`mt-3 ${OUTLINED_BUTTON}`}>
          Try again
        </button>
      </Message>
    );
  }
  return <Result channel={channel.data} />;
}

function Result({ channel }: { channel: ChannelDetail }) {
  return (
    <div className={CONTAINER}>
      <div className={HEADER}>
        <div className="min-w-0">
          <h1 className="line-clamp-2 font-hand text-[1.375rem] leading-tight font-semibold text-navy sm:text-2xl lg:text-[1.75rem]">
            {channel.name}
          </h1>
          <p className="mt-1 text-ink">{metaLine(channel.videos)}</p>
          <a
            href={`https://www.youtube.com/channel/${encodeURIComponent(channel.id)}`}
            target="_blank"
            rel="noopener noreferrer"
            className={TEXT_LINK}
          >
            <span>
              View on YouTube&nbsp;<span aria-hidden="true">↗</span>
              <span className="sr-only"> (opens in a new tab)</span>
            </span>
          </a>
        </div>
      </div>

      <ScorePanel
        score={channel.score}
        features={channel.features}
        subject="channel"
        className="mt-4"
        kid={<PanelKid />}
        scoreInfo={
          <p>
            Score 0–100: the average of this channel’s video scores. Each shows where a video’s
            production sits among the videos in our dataset. We measure production style only.
          </p>
        }
      />

      <OverYears channel={channel} />
    </div>
  );
}

/** The kid with the magnifying glass, peeking over the panel's top edge at its right end. */
function PanelKid() {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- static export, images pre-converted
    <img
      src={asset("/images/kid_lens_downward.webp")}
      alt=""
      aria-hidden="true"
      width={416}
      height={277}
      data-kid=""
      // The art's table edge is 84% down the image; it sits on the border. Its near-white
      // background is lifted to white, and multiplies with the line it overlaps.
      className="pointer-events-none absolute top-0 right-0 h-auto w-32 -translate-y-[84%] mix-blend-multiply brightness-[1.03] sm:right-4 sm:w-44 lg:right-8 lg:w-52"
    />
  );
}

/** Skeletons of the name, the score panel and the chart; also the Suspense fallback. */
export function Loading() {
  const bar = "block animate-pulse rounded bg-gray-200";
  return (
    <div className={CONTAINER} aria-busy="true">
      <h1 className="sr-only">{HEADING}</h1>
      <p role="status" className="sr-only">
        Loading channel…
      </p>
      <div className={HEADER}>
        <div className="min-w-0">
          <span className={`${bar} h-7 w-3/5`} />
          <span className={`${bar} mt-2 h-5 w-4/5`} />
          <span className={`${bar} mt-3 h-5 w-2/5`} />
        </div>
      </div>
      <ScorePanelSkeleton className="mt-4" />
      <div className={`mt-8 ${SECTION_CARD}`}>
        <span className={`${bar} h-8 w-2/3 max-w-80`} />
        <div className="mt-6 h-64 animate-pulse rounded-2xl bg-gray-200 sm:h-80" />
      </div>
    </div>
  );
}
