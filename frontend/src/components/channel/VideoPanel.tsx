"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import ScoreMeter from "@/components/ScoreMeter";
import YouTubePlayer from "@/components/YouTubePlayer";
import { OUTLINED_BUTTON, TEXT_LINK } from "@/components/video/parts";
import type { ChannelVideo } from "@/lib/api";
import { videoHref } from "@/lib/routes";
import { formatDate, measureName, pointOf, type Measure } from "./chart";

/**
 * The video opened from the over-years chart (see STYLE.md, Video panel): its preview, which plays
 * on click, and its value for the chart's measurement. When it opens, the page scrolls it into
 * view smoothly (at once with reduced motion) and it takes focus.
 */
export default function VideoPanel({
  video,
  measure,
  onClose,
}: {
  video: ChannelVideo;
  measure: Measure;
  onClose: () => void;
}) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = panel.current;
    if (!el) return;
    // Focus without the browser's instant jump; the scroll below glides there instead.
    el.focus({ preventScroll: true });
    const reduce = typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView?.({ behavior: reduce ? "auto" : "smooth", block: "nearest" });
  }, [video.id]);

  const point = pointOf(video, measure);
  return (
    <div
      ref={panel}
      tabIndex={-1}
      role="region"
      aria-labelledby="video-panel-title"
      className="mt-6 flex flex-col gap-4 rounded-2xl bg-sky p-4 sm:flex-row sm:gap-6 sm:p-5"
    >
      <div className="w-full shrink-0 sm:w-60">
        <YouTubePlayer key={video.id} id={video.id} title={video.title} />
      </div>
      <div className="min-w-0">
        <h3 id="video-panel-title" className="line-clamp-2 font-hand text-lg leading-snug font-semibold text-navy">
          {video.title}
        </h3>
        <p className="mt-1 text-sm text-ink">{formatDate(video.publishedAt)}</p>
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-semibold text-navy">{measureName(measure)}</span>
          {point.kind === "value" ? (
            <ScoreMeter score={point.value} size="compact" />
          ) : (
            <span className="text-sm text-ink/80">{point.text}</span>
          )}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-2">
          <Link href={videoHref(video.id)} className={TEXT_LINK}>
            Video details&nbsp;<span aria-hidden="true">→</span>
          </Link>
          <button type="button" onClick={onClose} className={OUTLINED_BUTTON}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
