import type { Metadata } from "next";
import PrivacyPage from "@/components/privacy/PrivacyPage";

export const metadata: Metadata = {
  title: "Privacy policy - HyperStim?",
  description: "What the HyperStim? website keeps about you, why, and for how long.",
  alternates: { canonical: "/privacy/" },
};

export default function Page() {
  return <PrivacyPage />;
}
