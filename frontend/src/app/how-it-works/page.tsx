import type { Metadata } from "next";
import HowItWorks from "@/components/how-it-works/HowItWorks";
import { pageMetadata } from "@/lib/site";

export const metadata: Metadata = pageMetadata({
  title: "How it works - HyperStim?",
  description:
    "How HyperStim? measures the production style of kids’ videos and turns 12 measurements into one score.",
  path: "how-it-works/",
});

export default function Page() {
  return <HowItWorks />;
}
