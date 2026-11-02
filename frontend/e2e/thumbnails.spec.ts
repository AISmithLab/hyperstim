import type { Page } from "@playwright/test";
import { channelVideos, topChannels } from "./api";
import { API } from "./backend";
import { expect, expectNoAxeViolations, isPhone, test } from "./fixtures";

// A thumbnail that can't load (e.g. the video is gone from YouTube) is a placeholder in its
// place, never the browser's broken image (plan 009, Thumbnails).

function escape(text: string) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+");
}

/** Our backend answers 404 for this video's thumbnails, as when YouTube no longer has them. */
async function gone(page: Page, id: string) {
  await page.route(
    (url) => url.href.startsWith(`${API}/api/thumbnails/${id}?`),
    (route) => route.fulfill({ status: 404, body: "" }),
  );
}

async function oldestVideo(request: Parameters<typeof channelVideos>[0]) {
  const [channel] = await topChannels(request);
  const videos = await channelVideos(request, channel.id);
  const video = [...videos].sort((a, b) => a.publishedAt.localeCompare(b.publishedAt))[0];
  return { channel, video, title: new RegExp(escape(video.title)) };
}

test.describe("a thumbnail that can't load", () => {
  test("is a placeholder on the channel page, the rest unchanged", async ({ page, request }) => {
    const { channel, video, title } = await oldestVideo(request);
    await gone(page, video.id);
    await page.goto(`/channel/?id=${channel.id}`);
    // From `sm` its thumbnail hangs under the chart; on phones it's the strip's first card.
    const holder = isPhone() ? page.getByRole("link", { name: title }).first() : page.getByRole("button", { name: title }).first();
    await holder.scrollIntoViewIfNeeded();
    const placeholder = holder.locator("[data-thumbnail-missing]");
    await expect(placeholder).toBeVisible();
    await expect(placeholder.locator("svg")).toBeVisible();
    await expect(holder.locator("img")).toHaveCount(0);
    // Another video's thumbnail still loads.
    const loaded = page.locator('img[src*="/api/thumbnails/"]').filter({ visible: true }).first();
    await expect(loaded).toHaveJSProperty("complete", true);
    expect(await loaded.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
    await expectNoAxeViolations(page);
  });

  test("leaves the video page's preview a plain tile that still plays", async ({ page, request, youtubeRequests }) => {
    const { video } = await oldestVideo(request);
    await gone(page, video.id);
    await page.goto(`/video/?id=${video.id}`);
    const play = page.getByRole("button", { name: /^Play video/ });
    await expect(play).toBeVisible();
    const placeholder = page.locator("[data-thumbnail-missing]");
    await expect(placeholder).toBeVisible();
    await expect(placeholder.locator("svg")).toHaveCount(0); // the Play button is in the middle
    await play.click();
    await expect.poll(() => youtubeRequests.length).toBeGreaterThan(0);
  });

  test("is a placeholder in the compare picker's suggestions", async ({ page, request }) => {
    const { video } = await oldestVideo(request);
    await gone(page, video.id);
    await page.goto("/compare/");
    const picker = page.getByRole("region", { name: "Video A" }).getByRole("combobox", { name: "Video name or video link" });
    await picker.fill(video.title);
    // Only its own suggestion (another video may share the title).
    const list = page.getByRole("listbox", { name: "Suggested videos" });
    await expect(list.getByRole("option").first()).toBeVisible();
    await expect(list.locator("[data-thumbnail-missing] svg")).toHaveCount(1);
    await expect(list.locator("[data-thumbnail-missing] svg")).toBeVisible();
  });
});
