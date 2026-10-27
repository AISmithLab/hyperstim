import { topVideos } from "./api";
import { expect, tabTo, test } from "./fixtures";

// The text pages: how it works, privacy and about.

test.describe("how it works", () => {
  test("its check field opens a video's page", async ({ page, request }) => {
    const [video] = await topVideos(request);
    await page.goto("/how-it-works/");
    const field = page.getByRole("textbox", { name: "YouTube link or video ID" });
    await field.fill(video.id);
    await field.press("Enter");
    await expect(page.getByRole("heading", { level: 1, name: video.title })).toBeVisible();
  });

  test("a question opens and closes by keyboard", async ({ page }) => {
    await page.goto("/how-it-works/");
    // A <summary> has no role to find it by.
    const question = page.locator("summary").first();
    await tabTo(page, question, 80);
    await page.keyboard.press("Enter");
    await expect(page.locator("details").first()).toHaveAttribute("open", "");
    await page.keyboard.press("Enter");
    await expect(page.locator("details").first()).not.toHaveAttribute("open");
  });
});

test.describe("privacy", () => {
  test("its cookie settings button opens the cookie choice", async ({ page }) => {
    await page.goto("/privacy/");
    await page.getByRole("main").getByRole("button", { name: "cookie settings" }).click();
    const banner = page.getByRole("region", { name: "Cookies on HyperStim?" });
    await expect(banner).toBeFocused();
    await expect(banner.getByText("Your current choice: rejected.")).toBeVisible();
  });
});

test.describe("about", () => {
  test("introduces the team", async ({ page }) => {
    await page.goto("/about/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("term").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Get in touch" })).toBeVisible();
  });
});
