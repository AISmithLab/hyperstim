import type { Metadata } from "next";
import { Suspense } from "react";
import ComparePage, { Loading } from "@/components/compare/ComparePage";
import { pageMetadata } from "@/lib/site";

export const metadata: Metadata = pageMetadata({
  title: "Compare - HyperStim?",
  description:
    "Put two kids’ videos or channels side by side and see where their production differs.",
  path: "compare/",
});

export default function Page() {
  // The state is read from the URL on the client; the Suspense boundary is required for the static export.
  return (
    <Suspense fallback={<Loading />}>
      <ComparePage />
    </Suspense>
  );
}
