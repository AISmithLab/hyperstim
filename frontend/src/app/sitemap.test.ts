import { readdirSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { fixedPages, siteUrl } from "@/lib/site";
import sitemap from "./sitemap";

// Pages that are filled in from ?id= and so aren't in the sitemap.
const DETAIL_PAGES = ["channel/", "video/"];

describe("sitemap", () => {
  it("lists every fixed page as an absolute URL", () => {
    expect(sitemap().map((entry) => entry.url)).toEqual(fixedPages.map((page) => `${siteUrl}${page}`));
  });

  it("covers every page in the app", () => {
    const appDir = import.meta.dirname;
    const pages = readdirSync(appDir)
      .filter((name) => statSync(path.join(appDir, name)).isDirectory())
      .map((name) => `${name}/`);
    expect([...fixedPages.filter(Boolean), ...DETAIL_PAGES].sort()).toEqual(pages.sort());
  });
});
