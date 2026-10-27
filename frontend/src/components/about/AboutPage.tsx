import type { ReactNode } from "react";
import { CONTACT_URL } from "@/components/privacy/PrivacyPage";
import { asset } from "@/lib/asset";

// The About page (plan 015): who makes the site and why, for parents. The text and the team on
// the page itself (no card), then the contact panel.

export const LAB_URL = "https://aismithlab.com";
/** In alphabetical order by last name. */
export const CONTRIBUTORS = ["Shao-Yu Chu", "Noel Mekogue"];
export const ADVISORS = ["Haojian Jin"];

const TEXT_LINK = "font-bold text-navy underline decoration-2 underline-offset-4 hover:decoration-sunny";

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 pt-8 sm:px-6 md:pt-12 lg:px-8">
      <h1 className="font-hand text-[2rem] leading-tight font-semibold text-navy sm:text-[2.75rem] lg:text-[3.25rem]">
        About us
      </h1>
      <div className="mt-4 space-y-4 text-lg leading-relaxed sm:mt-6">
        <p>
          While concerns about overstimulating children’s content are growing, parents often have limited information
          about how videos differ in their pacing, colors, motion, and sound.
        </p>
        <p>
          <Name /> is a research-based platform developed by the <External href={LAB_URL}>AI Smith Lab</External> at
          UC San Diego. By analyzing thousands of children’s YouTube videos, we measure their audiovisual stimulation
          levels and make the results accessible to parents for exploration and comparison.
        </p>
        <p>
          Our mission is to bring greater transparency to children’s digital media and empower families to make
          informed decisions about what their children watch.
        </p>
      </div>
      <dl className="mt-8 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1.5">
        <dt className="font-bold text-navy">Contributors</dt>
        <dd>{CONTRIBUTORS.join(", ")}</dd>
        <dt className="font-bold text-navy">{ADVISORS.length > 1 ? "Advisors" : "Advisor"}</dt>
        <dd>{ADVISORS.join(", ")}</dd>
      </dl>
      <Contact />
    </div>
  );
}

/**
 * "Get in touch" on a mint panel, with plants growing from its bottom edge and the kid waving
 * from its top edge (from `md`). The kid is as tall as the room left above the panel, so it
 * stays clear of the text: its head is the same size as on the other pages (STYLE.md).
 */
function Contact() {
  return (
    <section
      aria-labelledby="contact"
      className="relative mt-10 rounded-[2rem] bg-mint px-5 py-8 sm:px-8 md:mt-24 md:pb-28 lg:mt-32 xl:mt-40"
    >
      {/* Sitting on the panel's edge: the art's bottom 1 % is empty. */}
      {/* eslint-disable-next-line @next/next/no-img-element -- static export, images pre-converted */}
      <img
        src={asset("/images/kid_wave.webp")}
        alt=""
        aria-hidden="true"
        width={576}
        height={480}
        data-kid=""
        className="pointer-events-none absolute right-6 bottom-full hidden h-auto w-54 translate-y-[1%] md:block lg:w-61 xl:w-72"
      />
      <h2 id="contact" className="font-hand text-2xl font-semibold text-navy sm:text-3xl">
        Get in touch
      </h2>
      <p className="mt-3">
        Questions, corrections or ideas? Please fill out our <External href={CONTACT_URL}>contact form</External>.
      </p>
      <div aria-hidden="true" className="pointer-events-none absolute bottom-0 left-3 hidden items-end md:flex">
        {/* eslint-disable-next-line @next/next/no-img-element -- decorative */}
        <img src={asset("/images/grass_1.webp")} alt="" width={220} height={268} className="h-24 w-auto" />
        {/* eslint-disable-next-line @next/next/no-img-element -- decorative */}
        <img src={asset("/images/flower_1.webp")} alt="" width={260} height={239} className="-ml-4 h-20 w-auto" />
      </div>
      {/* eslint-disable-next-line @next/next/no-img-element -- decorative */}
      <img
        aria-hidden="true"
        src={asset("/images/flower_2.webp")}
        alt=""
        width={300}
        height={150}
        className="pointer-events-none absolute right-6 bottom-0 hidden h-20 w-auto md:block"
      />
    </section>
  );
}

/** The site's name in running text, bold italic (plan 015). */
function Name() {
  return <span className="font-bold italic">HyperStim?</span>;
}

function External({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={TEXT_LINK}>
      {children}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}
