"use client";

import Link from "next/link";
import RollingNumber from "@/components/RollingNumber";
import { asset } from "@/lib/asset";
import { useGrowth } from "@/lib/use-growth";

export default function Hero() {
  return (
    <section
      aria-labelledby="hero-heading"
      className="grid gap-6 md:grid-cols-[1fr_auto] md:items-center md:gap-x-8 md:gap-y-6 lg:grid-cols-[55fr_45fr] lg:gap-x-10"
    >
      <h1
        id="hero-heading"
        className="font-hand text-[2rem] leading-tight font-semibold text-balance text-navy sm:text-[2.75rem] md:col-start-1 md:row-start-1 md:self-end lg:text-[3.25rem]"
      >
        How stimulating are the videos <span className="marker">your child watches?</span>
      </h1>

      <div
        aria-hidden="true"
        className="hidden md:col-start-2 md:row-span-2 md:row-start-1 md:mx-auto md:block md:w-[21.5rem] lg:w-[24.5rem] xl:w-[29rem]"
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- static export, images pre-converted */}
        <img
          src={asset("/images/kid_1.webp")}
          alt=""
          width={928}
          height={464}
          className="h-auto w-full"
        />
      </div>

      <div className="max-w-prose text-lg md:col-start-1 md:row-start-2 md:self-start">
        <p>
          From rapid scene changes to bright colors and loud sounds, children’s videos vary in how
          stimulating they are.
        </p>
        <DatasetLine />
      </div>
    </section>
  );
}

/**
 * The dataset's size, growing while the page is open (plan 013; see STYLE.md, Growing counts). The
 * sentence and the pill are there from the first paint, with skeleton bars for the numbers, which then
 * count up; only if the counts can't be had does the sentence say "thousands of" instead.
 */
function DatasetLine() {
  const growth = useGrowth();
  if (growth === "failed") {
    return <p className="mt-4">Explore and compare thousands of videos to better understand what your child is watching.</p>;
  }
  const ready = growth !== "loading";
  return (
    <>
      <p className="mt-4" aria-busy={!ready}>
        Explore and compare{" "}
        <b className="font-bold text-navy">
          {ready ? <RollingNumber value={growth.videos} from={growth.from.videos} /> : <Room digits="00,000" />}
        </b>{" "}
        videos from{" "}
        <b className="font-bold text-navy">
          {ready ? <RollingNumber value={growth.channels} from={growth.from.channels} /> : <Room digits="000" />}
        </b>{" "}
        channels to better understand what your child is watching.
      </p>
      {!ready ? (
        <p className="mt-3">
          <span className={PILL}>
            +<Room digits="00" /> videos in the past week
          </span>
        </p>
      ) : (
        growth.pastWeek > 0 && (
          <p className="mt-3">
            {/* It lists the videos it counts (plan 013). */}
            <Link
              href={`/rankings?${new URLSearchParams({ q: growth.pastWeekQuery })}`}
              className={`${PILL} transition-colors hover:bg-sky-blue/25`}
            >
              +<RollingNumber value={growth.pastWeek} from={growth.from.pastWeek} /> videos in the past week
            </Link>
          </p>
        )
      )}
    </>
  );
}

const PILL = "inline-block rounded-full bg-sky px-3 py-0.5 text-sm font-bold whitespace-nowrap text-navy";

/** A skeleton bar where a number will be, as wide as `digits`, so nothing moves when it comes. */
function Room({ digits }: { digits: string }) {
  return (
    <span aria-hidden="true" className="animate-pulse rounded bg-gray-200 text-transparent tabular-nums">
      {digits}
    </span>
  );
}
