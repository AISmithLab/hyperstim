import type { Metadata } from "next";
import HowItWorks from "@/components/how-it-works/HowItWorks";

export const metadata: Metadata = {
  title: "How it works - HyperStim?",
  description:
    "How HyperStim? measures the production style of kids’ videos and turns 12 measurements into one score.",
  alternates: { canonical: "/how-it-works/" },
};

export default function Page() {
  return <HowItWorks />;
}
