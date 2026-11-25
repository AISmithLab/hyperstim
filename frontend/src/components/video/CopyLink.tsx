"use client";

import { useEffect, useState } from "react";
import { OUTLINED_BUTTON } from "./parts";

/** How long "Link copied" or "Couldn't copy" shows before the button reads "Copy link" again. */
export const COPIED_MS = 3000;

const LABEL = { idle: "Copy link", copied: "Link copied", failed: "Couldn’t copy" } as const;

/** Copies the page's address, for coming back to a check that waits (plan 004). */
export default function CopyLink({ announce }: { announce: (text: string) => void }) {
  const [state, setState] = useState<keyof typeof LABEL>("idle");

  useEffect(() => {
    if (state === "idle") return;
    const timer = setTimeout(() => setState("idle"), COPIED_MS);
    return () => clearTimeout(timer);
  }, [state]);

  async function copy() {
    let done: "copied" | "failed" = "copied";
    try {
      // Missing outside a secure context (plain http), and some in-app browsers refuse.
      await navigator.clipboard.writeText(window.location.href);
    } catch {
      done = "failed";
    }
    setState(done);
    announce(LABEL[done]);
  }

  return (
    <button type="button" onClick={copy} className={OUTLINED_BUTTON}>
      {LABEL[state]}
    </button>
  );
}
