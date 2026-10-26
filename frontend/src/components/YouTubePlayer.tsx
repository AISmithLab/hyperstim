"use client";

import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import { thumbnailUrl } from "@/lib/api";

const PLAYER_ORIGIN = "https://www.youtube-nocookie.com";
/** The player's "playing" state in the embed's message API. */
const PLAYING = 1;
/** How long the thumbnail stays over the player after its page has loaded, while it draws, in ms. */
const COVER_MS = 400;

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
 *
 * With `onStart`, the parent owns the playing state instead: the click calls `onStart`, and
 * `playing` shows the player (the video page moves it to a larger spot). With `cover`, the thumbnail
 * stays over the player until it has loaded, then fades out, so the box isn't black meanwhile.
 */
export default function YouTubePlayer({
  id,
  title,
  onPlay,
  ref,
  playing: playingProp,
  onStart,
  cover = false,
}: {
  id: string;
  title: string;
  onPlay?: () => void;
  ref?: Ref<PlayerHandle>;
  playing?: boolean;
  onStart?: () => void;
  cover?: boolean;
}) {
  const [started, setStarted] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const coverTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(coverTimer.current), []);
  const playing = playingProp ?? started;
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
        <>
          <iframe
            ref={frame}
            src={`${PLAYER_ORIGIN}/embed/${videoId}?autoplay=1${api}`}
            title={title}
            allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
            allowFullScreen
            onLoad={() => {
              if (controlled) send({ event: "listening", id: videoId, channel: "widget" });
              if (cover) coverTimer.current = setTimeout(() => setLoaded(true), COVER_MS);
            }}
            className="absolute inset-0 size-full"
          />
          {cover && (
            // eslint-disable-next-line @next/next/no-img-element -- static export, no image optimization
            <img
              src={thumbnailUrl(id)}
              alt=""
              width={480}
              height={360}
              data-cover=""
              className={`pointer-events-none absolute inset-0 size-full object-cover motion-safe:transition-opacity motion-safe:duration-300 ${loaded ? "opacity-0" : ""}`}
            />
          )}
        </>
      ) : (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element -- static export, no image optimization */}
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
              onClick={() => (onStart ? onStart() : setStarted(true))}
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
