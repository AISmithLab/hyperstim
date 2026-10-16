import type { ReactNode } from "react";
import { asset } from "@/lib/asset";

// The privacy policy (plan 009). Every statement must stay true: a change to what the site or the
// backend stores, logs, or loads from other companies updates this page in the same change.

export const LAST_UPDATED = "October 16, 2026";
export const CONTACT_URL = "https://forms.gle/oLbWLgE8sT6zHhLR9";
const GITHUB_PRIVACY = "https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement";
const GOOGLE_PRIVACY = "https://policies.google.com/privacy";

const TEXT_LINK = "font-bold text-navy underline decoration-2 underline-offset-4 hover:decoration-sunny";
const H2 = "scroll-mt-4 font-hand text-2xl font-semibold text-navy sm:text-3xl";

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 pt-8 sm:px-6 md:pt-12 lg:px-8">
      <Hero />
      <div className="rounded-[2rem] border border-navy/15 bg-white px-4 py-8 sm:px-8">
        <div className="divide-y divide-navy/10">
          <Section id="browsing" title="When you browse the site">
            <p>
              Our pages are hosted by GitHub Pages. Like any web host, GitHub receives your IP address and browser
              details, and logs which pages are requested. See <External href={GITHUB_PRIVACY}>GitHub’s privacy statement</External>.
            </p>
            <p>
              Scores and video details come from our own server. Its logs record each request: your IP address, the
              time, the address requested, and your browser. We use them to keep the site running and safe from abuse,
              and delete them after 14 days.
            </p>
            <p>The site’s fonts and pictures come with the site, not from other companies.</p>
          </Section>
          <Section id="checking" title="When you check a video">
            <p>
              When you check a video that isn’t in our dataset, our server downloads it from YouTube, measures it, and
              deletes the download as soon as it’s done.
            </p>
            <p>
              We keep the video’s ID, its public details (such as its title and channel), and its results, so anyone
              who checks it later gets them right away. We don’t save who checked it.
            </p>
            <p>
              When you compare channels and paste a channel link, our server may ask YouTube which channel it is.
              YouTube sees our server, not you.
            </p>
            <p>
              So that no one can overload the server, we count how many new checks and channel look-ups each IP
              address starts in an hour. The count is kept only in the server’s memory, is never saved, and is
              forgotten after an hour.
            </p>
          </Section>
          <Section id="youtube" title="YouTube">
            <p>
              Video thumbnails come from our server, which gets them from YouTube. So YouTube doesn’t see you while
              you browse.
            </p>
            <p>
              A video player loads only when you press “Play video”. It uses YouTube’s privacy-enhanced mode
              (youtube-nocookie.com). Once it has loaded, YouTube receives your IP address and may set cookies or
              store data in your browser, as described in <External href={GOOGLE_PRIVACY}>Google’s privacy policy</External>.
            </p>
          </Section>
          <Section id="cookies" title="Cookies">
            <p>
              We don’t set any cookies and don’t store anything in your browser. YouTube may, but only after you press
              play on a video.
            </p>
            <p>We don’t track you, so Do Not Track signals change nothing.</p>
          </Section>
          <Section id="children" title="Children">
            <p>
              This site is meant for parents and other adults. We don’t knowingly collect personal information from
              anyone, children included.
            </p>
          </Section>
          <Section id="your-choices" title="Your choices">
            <p>
              To ask what we hold about you, or to have it deleted, please fill out the <ContactLink /> form.
            </p>
          </Section>
        </div>
      </div>
    </div>
  );
}

/**
 * The H1 and the date, with the kid sitting on the policy card's top edge. The kid's head is as
 * large as on the other pages (STYLE.md), so it's taller than the text and rises above it into the
 * page's top padding instead of pushing the H1 down; the hero's minimum height keeps it clear of
 * the header.
 */
function Hero() {
  return (
    <div className="relative md:min-h-36 md:pr-64 lg:min-h-40 lg:pr-76 xl:min-h-48 xl:pr-88">
      <div className="pb-6">
        <h1 className="font-hand text-[2rem] leading-tight font-semibold text-navy sm:text-[2.75rem] lg:text-[3.25rem]">
          Privacy policy
        </h1>
        <p className="mt-2 text-ink">Last updated: {LAST_UPDATED}</p>
      </div>
      {/* Sitting on the card's edge: the art's bottom 1 % is empty. */}
      {/* eslint-disable-next-line @next/next/no-img-element -- static export, images pre-converted */}
      <img
        src={asset("/images/kid_quiet.webp")}
        alt=""
        aria-hidden="true"
        width={448}
        height={373}
        data-kid=""
        className="pointer-events-none absolute right-0 bottom-0 z-10 hidden h-auto w-54 translate-y-[1%] md:mr-8 md:block lg:mr-12 lg:w-61 xl:w-72"
      />
    </div>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="space-y-3 py-6 first:pt-0 last:pb-0">
      <h2 id={id} className={H2}>
        {title}
      </h2>
      {children}
    </section>
  );
}

function ContactLink() {
  return <External href={CONTACT_URL}>contact us</External>;
}

function External({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={TEXT_LINK}>
      {children}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}
