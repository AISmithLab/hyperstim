"use client";

import { useEffect, useRef, useState } from "react";
import { thumbnailUrl } from "@/lib/youtube";

/**
 * A video's YouTube thumbnail with a "Play video" button; the click (the visitor's consent)
 * swaps in the youtube-nocookie.com player in the same box. Nothing loads from the player
 * domain before the click.
 */
export default function YouTubePlayer({ id, title }: { id: string; title: string }) {
  const [playing, setPlaying] = useState(false);
  const frame = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    if (playing) frame.current?.focus();
  }, [playing]);

  const videoId = encodeURIComponent(id);
  return (
    <div className="@container relative aspect-video w-full overflow-hidden rounded-2xl bg-navy/10">
      {playing ? (
        <iframe
          ref={frame}
          src={`https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1`}
          title={title}
          allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
          allowFullScreen
          className="absolute inset-0 size-full"
        />
      ) : (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element -- external thumbnail, static export */}
          <img
            src={thumbnailUrl(id)}
            alt=""
            width={480}
            height={360}
            className="absolute inset-0 size-full object-cover"
          />
          <div className="absolute inset-0 flex items-center justify-center bg-navy/20">
            <button
              type="button"
              onClick={() => setPlaying(true)}
              // Icon only in a small preview; with its label from 20rem wide.
              className="flex size-12 items-center justify-center rounded-full bg-primary font-bold text-white hover:bg-navy @xs:w-auto @xs:gap-2 @xs:px-6"
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5 fill-current">
                <path d="M8 5.5v13a1 1 0 0 0 1.5.9l10.2-6.5a1 1 0 0 0 0-1.8L9.5 4.6A1 1 0 0 0 8 5.5Z" />
              </svg>
              <span className="sr-only @xs:not-sr-only">Play video</span>
              <span className="sr-only">: {title}</span>
            </button>
          </div>
        </>
      )}
    </div>
  );
}
