import { calmestVideo, topChannels, topVideos } from "./api";
import type { Page } from "@playwright/test";
import { expect, isPhone, tabTo, test } from "./fixtures";

/** The ranked list: a table on wider screens, a list on phones. */
function results(page: Page, kind: "Videos" | "Channels" = "Videos") {
  const name = new RegExp(`^${kind}, ranked by`);
  return page.getByRole("table", { name }).or(page.getByRole("list", { name }));
}

test.describe("rankings", () => {
  test("lists the most intense video first and opens it", async ({ page, request }) => {
    const [video] = await topVideos(request);
    await page.goto("/rankings/");
    const first = results(page).getByRole("link").first();
    await expect(first).toHaveAccessibleName(video.title.replace(/\s+/g, " "));
    await first.click();
    await expect(page.getByRole("heading", { level: 1, name: video.title })).toBeVisible();
  });

  test("calmest first puts the calmest video at the top", async ({ page, request }) => {
    const video = await calmestVideo(request);
    await page.goto("/rankings/");
    await page.getByRole("button", { name: /^Order:/ }).click();
    await expect(page).toHaveURL(/order=asc/);
    await expect(results(page).getByRole("link", { name: video.title, exact: true })).toBeVisible();
  });

  test("a category narrows the list and is kept in the link", async ({ page }) => {
    await page.goto("/rankings/");
    const showing = page.getByText(/^Showing 1–\d+ of /);
    await expect(showing).toHaveText(/ of [\d,]+ videos$/);
    const category = page.getByRole("group", { name: "Category" }).filter({ visible: true });
    // Below `sm` the chips become a select.
    if (await category.isVisible()) {
      await category.getByRole("button", { name: "Music" }).click();
      await expect(category.getByRole("button", { name: "Music" })).toHaveAttribute("aria-pressed", "true");
    } else {
      await page.getByRole("combobox", { name: "Category" }).selectOption({ label: "Music" });
    }
    await expect(page).toHaveURL(/music/);
    await expect(showing).toHaveText(/ of [\d,]+ music videos$/);
    await page.reload();
    await expect(showing).toHaveText(/ of [\d,]+ music videos$/);
  });

  test("search finds a video by its title, by keyboard", async ({ page, request }) => {
    const [video] = await topVideos(request);
    await page.goto("/rankings/");
    const search = page.getByRole("searchbox", { name: "Search videos" });
    await tabTo(page, search);
    await page.keyboard.type(video.title);
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/q=/);
    await expect(results(page).getByRole("link", { name: video.title, exact: true })).toBeVisible();
  });

  test("the channels view lists channels and opens one", async ({ page, request }) => {
    const [channel] = await topChannels(request);
    await page.goto("/rankings/");
    await page.getByRole("group", { name: "Show ranking of" }).getByRole("button", { name: "Channels" }).click();
    await expect(page).toHaveURL(/view=channels/);
    // The most intense channel first (the videos stay in view until the channels load).
    const first = results(page, "Channels").getByRole("link").first();
    await expect(first).toHaveAccessibleName(channel.name);
    await first.click();
    await expect(page.getByRole("heading", { level: 1, name: channel.name })).toBeVisible();
  });

  test("a measurement column sorts the list by it", async ({ page }) => {
    test.skip(isPhone(), "Phones pick the measurement elsewhere");
    await page.goto("/rankings/");
    await page.getByRole("columnheader", { name: "Rapid cutting" }).getByRole("button").click();
    await expect(page.getByRole("table", { name: /ranked by Rapid cutting/ })).toBeVisible();
  });
});
