import { channelVideos, topChannels } from "./api";
import { expect, isPhone, tabTo, test } from "./fixtures";

function escape(text: string) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+");
}

test.describe("channel", () => {
  test("shows the score and its videos over the years", async ({ page, request }) => {
    const [channel] = await topChannels(request);
    await page.goto(`/channel/?id=${channel.id}`);
    await expect(page.getByRole("heading", { level: 1, name: channel.name })).toBeVisible();
    await expect(page.getByText(`${channel.videoCount} videos in our dataset`, { exact: false })).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Stimulation score" }).getByText(`Stimulation score ${Math.round(channel.score)} out of 100`),
    ).toBeVisible();
    const table = page.getByRole("table", { name: `${channel.name}’s videos over the years` });
    // A header row plus one row per video.
    await expect(table.getByRole("row")).toHaveCount(channel.videoCount + 1);
  });

  test("a measurement chip switches the chart and table, by keyboard", async ({ page, request }) => {
    const [channel] = await topChannels(request);
    await page.goto(`/channel/?id=${channel.id}`);
    const years = page.getByRole("region", { name: "How it changed over years?" });
    await expect(years.getByRole("table")).toBeAttached();
    const chip = years.getByRole("button", { name: "Rapid cutting" }).filter({ visible: true });
    // Below `sm` the chips become a select.
    if (await chip.isVisible()) {
      await tabTo(page, chip, 60);
      await page.keyboard.press("Enter");
      await expect(chip).toHaveAttribute("aria-pressed", "true");
    } else {
      await years.getByRole("combobox").selectOption({ label: "Rapid cutting" });
    }
    // The chart's table for screen readers follows.
    await expect(years.getByRole("columnheader", { name: "Rapid cutting" })).toBeAttached();
  });

  test("opens one of its videos", async ({ page, request }) => {
    const [channel] = await topChannels(request);
    const [video] = await channelVideos(request, channel.id);
    await page.goto(`/channel/?id=${channel.id}`);
    const title = new RegExp(escape(video.title));
    if (isPhone()) {
      // Phones list the videos as cards under the chart, each a link to its page.
      await page.getByRole("link", { name: title }).first().click();
    } else {
      // Its thumbnail on the chart (two can share a title), by keyboard: thumbnails overlap,
      // so a click may land on a neighbour. It opens in the panel under the chart.
      await page.getByRole("button", { name: title }).first().focus();
      await page.keyboard.press("Enter");
      await page.getByRole("link", { name: /^Video details/ }).click();
    }
    await expect(page.getByRole("heading", { level: 1, name: video.title })).toBeVisible();
  });

  test("links to compare", async ({ page, request }) => {
    const [channel] = await topChannels(request);
    await page.goto(`/channel/?id=${channel.id}`);
    await page.getByRole("link", { name: "Compare with another channel" }).click();
    await expect(page.getByRole("region", { name: "Channel A" }).getByRole("link", { name: channel.name })).toBeVisible();
  });
});
