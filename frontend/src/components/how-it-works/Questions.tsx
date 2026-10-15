import Link from "next/link";
import type { ReactNode } from "react";
import { asset } from "@/lib/asset";
import { H2, TEXT_LINK } from "./parts";

// Common questions: the site's FAQ (the footer's FAQ link points here), as an accordion of native
// <details> on a mint panel (see STYLE.md, Accordion).

const QUESTIONS: [string, ReactNode][] = [
  [
    "What does a high score mean?",
    "A high score means a video is more intensely produced than most videos in our dataset. We measure production style only. We don’t judge a video’s content, educational value, or age appropriateness.",
  ],
  [
    "This video looks really intense. Why is its score low?",
    "We measure 5 minutes, starting 30 seconds in, not the whole video. If its busiest parts come later, the score won’t see them. And the score compares with other kids’ videos, many of which are intense too, so a video can feel busy and still sit in the middle.",
  ],
  [
    "What does “None detected” mean?",
    "Some measurements count events, like flashes or surprise sounds. Many videos have none at all. We mark those as “None detected”.",
  ],
  [
    "How is a channel’s score worked out?",
    "It’s the average of its videos’ scores in our dataset.",
  ],
  [
    "Do you keep anything about me?",
    <>
      When you check a video that isn’t in our dataset, we save its results, so anyone who checks it
      later gets them right away. Nothing about who checked it is saved. Our server keeps short-lived
      logs to prevent abuse. See our{" "}
      <Link href="/privacy" className={TEXT_LINK}>
        privacy policy
      </Link>
      .
    </>,
  ],
];

export default function Questions() {
  return (
    <section
      id="questions"
      aria-labelledby="questions-heading"
      className="relative scroll-mt-4 rounded-[2rem] bg-mint px-5 py-8 sm:px-8 md:pb-28"
    >
      <h2 id="questions-heading" className={`text-center ${H2}`}>
        Common questions
      </h2>
      <div className="mx-auto mt-6 max-w-3xl">
        {QUESTIONS.map(([question, answer]) => (
          <details key={question} className="group border-b border-navy/10 last:border-0">
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-4 py-2 font-semibold text-navy [&::-webkit-details-marker]:hidden">
              {question}
              <svg
                aria-hidden="true"
                viewBox="0 0 24 24"
                className="size-5 shrink-0 transition-transform group-open:rotate-180 motion-reduce:transition-none"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M6 9l6 6 6-6" />
              </svg>
            </summary>
            <p className="pb-4">{answer}</p>
          </details>
        ))}
      </div>

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
