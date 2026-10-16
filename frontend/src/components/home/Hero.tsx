import { asset } from "@/lib/asset";
import DatasetCount from "./DatasetCount";

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
          <i>HyperStim?</i> measures the production style of children’s videos: how fast they cut, how
          loud they get, and how saturated the colors are.
        </p>
        <p className="mt-4">
          See how any video compares with <DatasetCount /> other kids’ videos.
        </p>
      </div>
    </section>
  );
}
