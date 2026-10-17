import type { MetadataRoute } from "next";
import { fixedPages, siteUrl } from "@/lib/site";

// Written to out/sitemap.xml at build time (static export).
export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return fixedPages.map((page) => ({ url: `${siteUrl}${page}` }));
}
