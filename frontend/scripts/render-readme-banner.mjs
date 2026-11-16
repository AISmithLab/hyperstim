// Renders .github/readme/banner.html to banner.png, the README header (plan 001). Run from frontend/: node scripts/render-readme-banner.mjs
import { chromium } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../.github/readme");
const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 2 });
await page.goto(`file://${path.join(dir, "banner.html")}`);
await page.evaluate(() => document.fonts.ready);
await page.locator(".banner").screenshot({ path: path.join(dir, "banner.png"), omitBackground: true });
await browser.close();
