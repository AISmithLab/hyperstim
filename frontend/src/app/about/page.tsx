import type { Metadata } from "next";
import AboutPage from "@/components/about/AboutPage";
import { pageMetadata } from "@/lib/site";

export const metadata: Metadata = pageMetadata({
  title: "About - HyperStim?",
  description: "Who makes HyperStim?, why we built it, and how to get in touch.",
  path: "about/",
});

export default function Page() {
  return <AboutPage />;
}
