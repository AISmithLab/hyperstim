import Link from "next/link";
import type { ReactNode } from "react";
import { asset } from "@/lib/asset";

// Pieces shared by the video and channel pages' states.

export const CONTAINER = "mx-auto max-w-6xl px-4 pt-6 sm:px-6 lg:px-8";
export const OUTLINED_BUTTON =
  "min-h-11 rounded-full border-2 border-navy px-5 font-semibold text-navy hover:bg-white";
const MESSAGE_BOX = "mx-auto max-w-2xl rounded-2xl bg-sky p-6 text-center";
export const TEXT_LINK =
  "inline-flex min-h-11 items-center font-bold text-navy underline decoration-2 underline-offset-4 hover:decoration-sunny";

/** States without a result: a visually hidden H1 and a message box. */
export function Message({ children, heading = "Video details" }: { children: ReactNode; heading?: string }) {
  return (
    <div className={CONTAINER}>
      <h1 className="sr-only">{heading}</h1>
      <div className={MESSAGE_BOX}>{children}</div>
    </div>
  );
}

/**
 * A message box with the kid (and teddy) peeking over it: a video being or failing to be checked
 * live, or a channel we don't have. `heading` adds a visually hidden H1 for boxes without one.
 */
export function KidMessage({ children, heading }: { children: ReactNode; heading?: string }) {
  return (
    <div className={CONTAINER}>
      {heading && <h1 className="sr-only">{heading}</h1>}
      {/* eslint-disable-next-line @next/next/no-img-element -- static export, images pre-converted */}
      <img
        src={asset("/images/kid_2.webp")}
        alt=""
        aria-hidden="true"
        width={560}
        height={280}
        data-kid=""
        className="mx-auto hidden h-auto w-[280px] md:block"
      />
      <div className={MESSAGE_BOX}>{children}</div>
    </div>
  );
}

export function WatchOnYouTube({ id }: { id: string }) {
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

export function CheckAnother({ label = "Check another video" }: { label?: string }) {
  return (
    <Link href="/" className={TEXT_LINK}>
      {label}&nbsp;<span aria-hidden="true">→</span>
    </Link>
  );
}
