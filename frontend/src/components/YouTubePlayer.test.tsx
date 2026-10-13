import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import YouTubePlayer from "./YouTubePlayer";

describe("YouTubePlayer", () => {
  it("shows only the thumbnail until Play is clicked, then the player in focus", async () => {
    const user = userEvent.setup();
    const { container } = render(<YouTubePlayer id="dQw4w9WgXcQ" title="Snail time" />);

    expect(container.querySelector("iframe")).toBeNull();
    expect(container.innerHTML).not.toContain("youtube-nocookie.com");
    expect(container.querySelector("img")).toHaveAttribute("src", "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg");

    await user.click(screen.getByRole("button", { name: "Play video: Snail time" }));

    const frame = screen.getByTitle("Snail time");
    expect(frame).toHaveAttribute("src", "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?autoplay=1");
    expect(frame).toHaveFocus();
    expect(container.querySelector("img")).toBeNull();
  });
});
