import type { Metadata } from "next";
import CheckVideoCard from "@/components/home/CheckVideoCard";
import Hero from "@/components/home/Hero";
import RankingsCard from "@/components/home/RankingsCard";

export const metadata: Metadata = {
  title: "HyperStim? - How stimulating are kids’ videos?",
  description: "See how fast, loud, and intense children’s YouTube videos are.",
};

export default function HomePage() {
  return (
    <div className="mx-auto max-w-6xl px-4 pt-8 sm:px-6 md:pt-12 lg:px-8">
      <Hero />
      <div className="mt-12 grid items-start gap-16 md:mt-16 lg:grid-cols-[45fr_55fr] lg:gap-8">
        <CheckVideoCard />
        <RankingsCard />
      </div>
    </div>
  );
}
