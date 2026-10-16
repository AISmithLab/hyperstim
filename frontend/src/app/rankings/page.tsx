import type { Metadata } from "next";
import { Suspense } from "react";
import RankingsPage, { Loading } from "@/components/rankings/RankingsPage";

export const metadata: Metadata = {
  title: "Stimulation rankings - HyperStim?",
  description: "Every video and channel in our dataset, ranked by how intense its production is.",
};

export default function Page() {
  // The state is read from the URL on the client; the Suspense boundary is required for the static export.
  return (
    <Suspense fallback={<Loading />}>
      <RankingsPage />
    </Suspense>
  );
}
