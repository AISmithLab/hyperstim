import { topChannels, topVideos } from "./api";
import { ANALYZED } from "./backend";
import { expect, tabTo, test } from "./fixtures";

test.describe("home", () => {
  test("checking a dataset video by its link opens its page, by keyboard", async ({ page, request }) => {
    const [video] = await topVideos(request);
    await page.goto("/");
    const field = page.getByRole("textbox", { name: "YouTube link or video ID" });
    await tabTo(page, field);
    await page.keyboard.type(`https://www.youtube.com/watch?v=${video.id}&t=42s`);
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(`/video/?id=${video.id}`);
    await expect(page.getByRole("heading", { level: 1, name: video.title })).toBeVisible();
  });

  test("a finished live check opens with its score", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("textbox", { name: "YouTube link or video ID" }).fill(`youtu.be/${ANALYZED.id}`);
    await page.getByRole("button", { name: "Check video" }).click();
    await expect(page.getByRole("heading", { level: 1, name: ANALYZED.title })).toBeVisible();
    await expect(page.getByText(/^Stimulation score \d+ out of 100$/)).toBeVisible();
    // Its channel isn't in the dataset, so it has no page to link to.
    await expect(page.getByText(ANALYZED.channel)).toBeVisible();
    await expect(page.getByRole("link", { name: ANALYZED.channel })).toHaveCount(0);
  });

  test("a link that isn't YouTube's shows an error at the field", async ({ page }) => {
    await page.goto("/");
    const field = page.getByRole("textbox", { name: "YouTube link or video ID" });
    await field.fill("https://example.com/watch?v=nothing");
    await page.getByRole("button", { name: "Check video" }).click();
    await expect(field).toHaveAttribute("aria-invalid", "true");
    await expect(field).not.toHaveAccessibleDescription("");
    await expect(page).toHaveURL("/");
  });

  test("the rankings card shows the most intense videos and channels", async ({ page, request }) => {
    const [video] = await topVideos(request);
    const [channel] = await topChannels(request);
    await page.goto("/");
    const card = page.getByRole("region", { name: "Stimulation rankings" });
    await expect(card.getByRole("link", { name: video.title, exact: true })).toBeVisible();
    await card.getByRole("button", { name: "Channels" }).click();
    await expect(card.getByRole("button", { name: "Channels" })).toHaveAttribute("aria-pressed", "true");
    await expect(card.getByRole("link", { name: channel.name, exact: true })).toBeVisible();
    await card.getByRole("link", { name: "See full rankings" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Stimulation rankings" })).toBeVisible();
  });

  test("the hero counts the dataset", async ({ page }) => {
    await page.goto("/");
    // The numbers count up; wait for the final ones.
    await expect(page.getByText(/Explore and compare [\d,]+ videos from [\d,]+ channels/)).toBeVisible();
  });
});
