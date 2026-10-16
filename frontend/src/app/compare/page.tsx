import type { Metadata } from "next";
import { Suspense } from "react";
import ComparePage, { Loading } from "@/components/compare/ComparePage";

export const metadata: Metadata = {
  title: "Compare - HyperStim?",
  description: "Put two kids’ videos or channels side by side and see where their production differs.",
};

export default function Page() {
  // The state is read from the URL on the client; the Suspense boundary is required for the static export.
  return (
    <Suspense fallback={<Loading />}>
      <ComparePage />
    </Suspense>
  );
}
