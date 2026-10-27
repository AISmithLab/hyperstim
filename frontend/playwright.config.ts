import { defineConfig, devices } from "@playwright/test";
import { API_PORT, GA_ID, prepareBackendDirs, SITE_PORT } from "./e2e/backend";

// End-to-end tests (plan 012): the built static site against the real backend with the
// committed reference set. Both servers are started here; `npm run test:e2e` builds the site.
const dirs = prepareBackendDirs();
const CI = !!process.env.CI;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  reporter: CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${SITE_PORT}`,
    trace: "retain-on-failure",
  },
  // Both engines at both widths: people use Safari on desktops and Chrome on phones too.
  // Phones at the width STYLE.md checks; tests tell them apart by the name's ending.
  projects: [
    { name: "chromium-desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } },
    { name: "webkit-desktop", use: { ...devices["Desktop Safari"], viewport: { width: 1280, height: 800 } } },
    { name: "chromium-phone", use: { ...devices["Pixel 7"], viewport: { width: 360, height: 740 } } },
    { name: "webkit-phone", use: { ...devices["iPhone 13"], viewport: { width: 360, height: 740 } } },
  ],
  webServer: [
    {
      command: "uv run uvicorn --factory hyperstim_api.main:create_app --port " + API_PORT,
      cwd: "../backend",
      url: `http://localhost:${API_PORT}/api/health`,
      reuseExistingServer: !CI,
      timeout: 120_000,
      env: {
        DATASET_PATH: "data/videos.tsv",
        // Only the reference set, so the server's daily data commits don't move what tests see.
        COLLECTED_DIR: "",
        CORS_ORIGIN: `http://localhost:${SITE_PORT}`,
        ANALYSIS_DIR: dirs.analysis,
        THUMBNAIL_DIR: dirs.thumbnails,
        USAGE_DIR: "",
        ANALYSIS_LIMIT_PER_IP: "0",
        ANALYSIS_LIMIT_PER_DAY: "0",
        API_DOCS: "0",
        YOUTUBE_API_KEY: "",
        YTDLP_COOKIES: "",
      },
    },
    {
      // Builds the static export for this backend, then serves it like GitHub Pages
      // (`trailingSlash` gives each page an index.html).
      command: `npm run build && uv run --project ../backend python -m http.server ${SITE_PORT} --directory out`,
      url: `http://localhost:${SITE_PORT}/`,
      reuseExistingServer: !CI,
      timeout: 300_000,
      // Set here so they win over a developer's .env.local.
      env: {
        NEXT_PUBLIC_API_BASE: `http://localhost:${API_PORT}`,
        NEXT_PUBLIC_API_MOCK: "",
        NEXT_PUBLIC_BASE_PATH: "",
        NEXT_PUBLIC_SITE_ORIGIN: "",
        NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION: "",
        // A made-up ID, so the consent banner works as in prod; Google's tag itself never loads.
        NEXT_PUBLIC_GA_ID: GA_ID,
      },
    },
  ],
});
