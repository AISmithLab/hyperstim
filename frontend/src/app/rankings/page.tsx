import type { Metadata } from "next";
import { Suspense } from "react";
import RankingsPage, { Loading } from "@/components/rankings/RankingsPage";
import { pageMetadata } from "@/lib/site";

export const metadata: Metadata = pageMetadata({
  title: "Stimulation rankings - HyperStim?",
  description: "Every video and channel in our dataset, ranked by how intense its production is.",
  path: "rankings/",
});

export default function Page() {
  // The state is read from the URL on the client; the Suspense boundary is required for the static export.
  return (
    <Suspense fallback={<Loading />}>
      <RankingsPage />
    </Suspense>
  );
}
