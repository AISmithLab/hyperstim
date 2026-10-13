import { asset } from "@/lib/asset";
import DatasetCount from "./DatasetCount";

export default function Hero() {
  return (
    <section
      aria-labelledby="hero-heading"
      className="grid gap-6 md:gap-8 lg:grid-cols-[55fr_45fr] lg:items-center lg:gap-x-10"
    >
      <h1
        id="hero-heading"
        className="font-hand text-[2rem] leading-tight font-semibold text-balance text-navy sm:text-[2.75rem] lg:col-start-1 lg:row-start-1 lg:self-end lg:text-[3.25rem]"
      >
        How stimulating are the videos <span className="marker">your child watches?</span>
      </h1>

      <div
        aria-hidden="true"
        className="md:order-last md:mx-auto md:w-[70%] lg:order-none lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:w-full"
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- static export, images pre-converted */}
        <img
          src={asset("/images/kid_1.webp")}
          alt=""
          width={1120}
          height={560}
          className="h-auto w-full"
        />
      </div>

      <div className="max-w-prose text-lg lg:col-start-1 lg:row-start-2 lg:self-start">
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
