import CheckVideoForm from "@/components/CheckVideoForm";
import { asset } from "@/lib/asset";
import { Lead, Section } from "./parts";
import Questions from "./Questions";
import Sampling from "./Sampling";
import Score from "./Score";
import WhatWeMeasure from "./WhatWeMeasure";

// The How it works page (plan 006): one video through a check, steps 1–4, then common questions.

export default function HowItWorks() {
  return (
    <div className="mx-auto max-w-6xl px-4 pt-8 sm:px-6 md:pt-12 lg:px-8">
      <Hero />
      <div className="grid gap-8">
        <PasteLink />
        <WhatWeMeasure />
        <Sampling />
        <Score />
        <Questions />
      </div>
    </div>
  );
}

/** The H1, and the kid lying on the first card's top edge. */
function Hero() {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <h1 className="font-hand text-[2rem] leading-tight font-semibold text-navy sm:text-[2.75rem] lg:text-[3.25rem]">
        How it works
      </h1>
      {/* Elbows and laptop rest on the card's border (the art's floor is 86 % down the image); from sm
          its top (13 % down) lines up with the H1's letters. */}
      {/* eslint-disable-next-line @next/next/no-img-element -- static export, images pre-converted */}
      <img
        aria-hidden="true"
        src={asset("/images/kid_wonder.webp")}
        alt=""
        width={960}
        height={640}
        className="relative z-10 mx-auto -mb-5 h-auto w-52 sm:mx-0 sm:mr-8 sm:-mt-4 sm:-mb-10 sm:w-64 lg:-mb-11 lg:w-[19rem]"
      />
    </div>
  );
}

/**
 * Step 1: a slim card with the real check field on the right, on the home card's butter so people
 * see it's the same thing. Title and sentence on the left from lg; stacked below.
 */
function PasteLink() {
  return (
    <Section
      id="paste"
      title="Paste a link"
      step={1}
      className="lg:grid lg:grid-cols-[1fr_auto] lg:grid-rows-[auto_1fr] lg:items-start lg:gap-x-10"
    >
      <Lead>Paste any YouTube video made for kids.</Lead>
      {/* From lg, its field is as long as the home card's at full width (a 411 px form). */}
      <div className="mt-6 rounded-2xl bg-butter px-5 pt-5 pb-1 lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:mt-0 lg:w-[28.25rem]">
        <CheckVideoForm />
      </div>
    </Section>
  );
}
