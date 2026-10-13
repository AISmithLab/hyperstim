"use client";

import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";
import InfoTip from "@/components/InfoTip";
import { asset } from "@/lib/asset";
import { parseVideoInput } from "@/lib/youtube";

const ERRORS = {
  empty: "Paste a YouTube link or video ID first.",
  invalid: "That doesn’t look like a YouTube link or video ID.",
};

export default function CheckVideoCard() {
  const router = useRouter();
  const id = useId();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const result = parseVideoInput(value);
    if (!result.ok) {
      setError(ERRORS[result.reason]);
      return;
    }
    setError(null);
    router.push(`/video?id=${encodeURIComponent(result.id)}`);
  }

  return (
    <section
      aria-labelledby={`${id}-heading`}
      className="relative rounded-[2rem] bg-butter px-5 py-8 sm:px-8 md:pb-24"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 id={`${id}-heading`} className="font-hand text-2xl font-semibold text-navy sm:text-3xl">
          Check a video
        </h2>
        <InfoTip id={`${id}-info`} label="More about checking a video">
          <p>Paste a YouTube link or video ID to see its stimulation score.</p>
          <p className="mt-2">Works best with children’s videos up to 15 minutes.</p>
        </InfoTip>
      </div>

      <form noValidate onSubmit={onSubmit} className="mt-6">
        <label htmlFor={`${id}-input`} className="block font-semibold text-navy">
          YouTube link or video ID
        </label>
        <div className="mt-2 flex flex-col gap-3 md:flex-row">
          <input
            id={`${id}-input`}
            type="text"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            placeholder="https://www.youtube.com/watch?v=…"
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              if (error) setError(null);
            }}
            aria-invalid={error ? true : undefined}
            aria-describedby={`${id}-error ${id}-info`}
            className="h-12 w-full min-w-0 rounded-full border-2 border-navy bg-white px-5 text-navy placeholder:text-ink/70 focus:shadow-[0_0_0_5px_var(--color-sunny)] focus:outline-none aria-invalid:border-error md:flex-1"
          />
          <button
            type="submit"
            className="h-12 shrink-0 rounded-full bg-primary px-6 font-bold text-white hover:bg-navy"
          >
            Check video <span aria-hidden="true">→</span>
          </button>
        </div>
        <p id={`${id}-error`} aria-live="polite" className="mt-2 min-h-6 font-semibold text-error">
          {error}
        </p>
      </form>

      <div aria-hidden="true" className="pointer-events-none absolute bottom-0 left-3 hidden items-end md:flex">
        {/* eslint-disable-next-line @next/next/no-img-element -- decorative */}
        <img src={asset("/images/grass_1.webp")} alt="" width={220} height={268} className="h-24 w-auto" />
        {/* eslint-disable-next-line @next/next/no-img-element -- decorative */}
        <img src={asset("/images/flower_1.webp")} alt="" width={260} height={239} className="-ml-4 h-20 w-auto" />
      </div>
    </section>
  );
}
