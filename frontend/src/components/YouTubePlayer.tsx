"use client";

import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import { thumbnailUrl } from "@/lib/youtube";

const PLAYER_ORIGIN = "https://www.youtube-nocookie.com";
/** The player's "playing" state in the embed's message API. */
const PLAYING = 1;

/** Controls a player from outside: pausing it does nothing until it has been started. */
export type PlayerHandle = { pause: () => void };

/**
 * A video's YouTube thumbnail with a "Play video" button; the click (the visitor's consent)
 * swaps in the youtube-nocookie.com player in the same box. Nothing loads from the player
 * domain before the click.
 *
 * With `onPlay`, the player also reports when it starts playing (also after a pause), and `ref`
 * can pause it, through the embed's message API; no script is loaded from YouTube. The compare
 * page uses this to play one video at a time.
 */
export default function YouTubePlayer({
  id,
  title,
  onPlay,
  ref,
}: {
  id: string;
  title: string;
  onPlay?: () => void;
  ref?: Ref<PlayerHandle>;
}) {
  const [playing, setPlaying] = useState(false);
  const frame = useRef<HTMLIFrameElement>(null);
  const controlled = onPlay !== undefined;
  // The latest callback, so a new function from the parent doesn't count as a new start.
  const onPlayRef = useRef(onPlay);
  useEffect(() => {
    onPlayRef.current = onPlay;
  });

  const send = (message: object) =>
    frame.current?.contentWindow?.postMessage(JSON.stringify(message), PLAYER_ORIGIN);

  useImperativeHandle(ref, () => ({ pause: () => send({ event: "command", func: "pauseVideo", args: [] }) }), []);

  useEffect(() => {
    if (playing) frame.current?.focus();
  }, [playing]);

  // The player's state changes, reported once it has been told someone is listening (on load).
  useEffect(() => {
    if (!playing || !controlled) return;
    onPlayRef.current?.(); // the click that started it
    let last: unknown = PLAYING;
    const onMessage = (e: MessageEvent) => {
      if (e.origin !== PLAYER_ORIGIN || e.source !== frame.current?.contentWindow) return;
      let data: { event?: string; info?: unknown } | null = null;
      try {
        data = typeof e.data === "string" ? JSON.parse(e.data) : e.data;
      } catch {
        return;
      }
      const state =
        data?.event === "onStateChange"
          ? data.info
          : data?.event === "infoDelivery"
            ? (data.info as { playerState?: unknown } | null)?.playerState
            : undefined;
      if (state === undefined) return;
      if (state === PLAYING && last !== PLAYING) onPlayRef.current?.();
      last = state;
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [playing, controlled]);

  const videoId = encodeURIComponent(id);
  const api = controlled ? `&enablejsapi=1&origin=${encodeURIComponent(window.location.origin)}` : "";
  return (
    <div className="@container relative aspect-video w-full overflow-hidden rounded-2xl bg-navy/10">
      {playing ? (
        <iframe
          ref={frame}
          src={`${PLAYER_ORIGIN}/embed/${videoId}?autoplay=1${api}`}
          title={title}
          allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
          allowFullScreen
          onLoad={controlled ? () => send({ event: "listening", id: videoId, channel: "widget" }) : undefined}
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
