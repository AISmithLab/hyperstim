/** The site's public URL (origin + basePath), with a trailing slash. Localhost when unset. */
export const siteUrl = `${process.env.NEXT_PUBLIC_SITE_ORIGIN || "http://localhost:3000"}${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/`;

/** The fixed pages, relative to siteUrl, as listed in the sitemap (plan 011). */
export const fixedPages = ["", "rankings/", "compare/", "how-it-works/", "privacy/"];
