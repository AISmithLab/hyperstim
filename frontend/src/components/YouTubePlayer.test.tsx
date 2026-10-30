import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRef } from "react";
import { describe, expect, it, vi } from "vitest";
import { expectNoAxeViolations } from "@/test/axe";
import YouTubePlayer, { type PlayerHandle } from "./YouTubePlayer";

describe("YouTubePlayer", () => {
  it("shows only the thumbnail until Play is clicked, then the player in focus", async () => {
    const user = userEvent.setup();
    const { container } = render(<YouTubePlayer id="dQw4w9WgXcQ" title="Snail time" />);

    expect(container.querySelector("iframe")).toBeNull();
    expect(container.innerHTML).not.toContain("youtube-nocookie.com");
    expect(container.querySelector("img")).toHaveAttribute("src", "/api/thumbnails/dQw4w9WgXcQ?size=hq");

    await user.click(screen.getByRole("button", { name: "Play video: Snail time" }));

    const frame = screen.getByTitle("Snail time");
    expect(frame).toHaveAttribute("src", "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?autoplay=1&playsinline=1");
    expect(frame).toHaveFocus();
    expect(container.querySelector("img")).toBeNull();
  });

  // Before Play only: axe can't reach into jsdom's iframe once the player is there.
  it("has no accessibility violations", async () => {
    render(<YouTubePlayer id="dQw4w9WgXcQ" title="Snail time" />);
    await expectNoAxeViolations();
  });
});

describe("YouTubePlayer with onStart", () => {
  it("leaves the playing state to its parent", async () => {
    const user = userEvent.setup();
    const onStart = vi.fn();
    const { container, rerender } = render(<YouTubePlayer id="dQw4w9WgXcQ" title="Snail time" onStart={onStart} />);

    await user.click(screen.getByRole("button", { name: "Play video: Snail time" }));
    expect(onStart).toHaveBeenCalledTimes(1);
    expect(container.querySelector("iframe")).toBeNull();

    rerender(<YouTubePlayer id="dQw4w9WgXcQ" title="Snail time" playing />);
    expect(screen.getByTitle("Snail time")).toHaveFocus();
  });
});

describe("YouTubePlayer with cover", () => {
  it("keeps the thumbnail over the player until it has loaded", () => {
    vi.useFakeTimers();
    const { container } = render(<YouTubePlayer id="dQw4w9WgXcQ" title="Snail time" playing cover />);
    const cover = container.querySelector("img[data-cover]");
    expect(cover).toHaveAttribute("src", "/api/thumbnails/dQw4w9WgXcQ?size=hq");
    expect(cover).not.toHaveClass("opacity-0");

    act(() => {
      screen.getByTitle("Snail time").dispatchEvent(new Event("load"));
    });
    expect(cover).not.toHaveClass("opacity-0");
    act(() => vi.advanceTimersByTime(400));
    expect(cover).toHaveClass("opacity-0", "pointer-events-none");
    vi.useRealTimers();
  });
});

describe("YouTubePlayer with onPlay", () => {
  it("reports each start, and pauses through the embed's message API", async () => {
    const user = userEvent.setup();
    const onPlay = vi.fn();
    const ref = createRef<PlayerHandle>();
    render(<YouTubePlayer id="dQw4w9WgXcQ" title="Snail time" onPlay={onPlay} ref={ref} />);

    await user.click(screen.getByRole("button", { name: "Play video: Snail time" }));
    const frame = screen.getByTitle("Snail time") as HTMLIFrameElement;
    expect(frame.src).toContain("enablejsapi=1");
    expect(onPlay).toHaveBeenCalledTimes(1);

    const player = frame.contentWindow!;
    const post = vi.spyOn(player, "postMessage").mockImplementation(() => {});
    const report = (state: number) =>
      act(() => {
        window.dispatchEvent(
          new MessageEvent("message", {
            origin: "https://www.youtube-nocookie.com",
            source: player,
            data: JSON.stringify({ event: "infoDelivery", info: { playerState: state } }),
          }),
        );
      });
    report(1); // still the same start
    report(2); // paused
    report(1); // playing again
    expect(onPlay).toHaveBeenCalledTimes(2);

    ref.current!.pause();
    expect(post).toHaveBeenCalledWith(
      JSON.stringify({ event: "command", func: "pauseVideo", args: [] }),
      "https://www.youtube-nocookie.com",
    );
  });
});
