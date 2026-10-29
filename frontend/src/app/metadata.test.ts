import { describe, expect, it } from "vitest";
import type { Metadata } from "next";
import { fixedPages } from "@/lib/site";

// Every page, as its folder in app/ ("" = home); detail pages are filled in from ?id=.
const PAGES = [...fixedPages, "channel/", "video/"];

const modules = import.meta.glob<{ metadata: Metadata }>("./**/page.tsx");

async function metadataOf(page: string): Promise<Metadata> {
  return (await modules[`./${page}page.tsx`]()).metadata;
}

describe("page metadata (plan 011)", () => {
  it.each(PAGES)("gives /%s link preview tags matching its title and description", async (page) => {
    const metadata = await metadataOf(page);
    expect(metadata.openGraph).toMatchObject({
      siteName: "HyperStim?",
      title: metadata.title,
      description: metadata.description,
    });
    expect(metadata.openGraph?.images).toEqual([
      expect.objectContaining({ url: "/og-image.png", width: 1200, height: 630 }),
    ]);
    expect(metadata.twitter).toMatchObject({ card: "summary_large_image" });
  });

  it.each(PAGES)("gives /%s a description short enough for search results", async (page) => {
    const { description } = await metadataOf(page);
    expect(description?.length).toBeGreaterThan(0);
    expect(description?.length).toBeLessThanOrEqual(155);
  });

  it.each(fixedPages)("gives /%s the same preview URL as its canonical URL", async (page) => {
    const metadata = await metadataOf(page);
    expect(metadata.alternates?.canonical).toBe(`/${page}`);
    expect(metadata.openGraph?.url).toBe(`/${page}`);
  });

  it.each(["channel/", "video/"])("gives /%s no canonical or preview URL", async (page) => {
    const metadata = await metadataOf(page);
    expect(metadata.alternates?.canonical).toBeUndefined();
    expect(metadata.openGraph?.url).toBeUndefined();
  });
});
