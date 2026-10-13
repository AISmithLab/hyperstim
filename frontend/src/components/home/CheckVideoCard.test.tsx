import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CheckVideoCard from "./CheckVideoCard";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

beforeEach(() => push.mockReset());

describe("CheckVideoCard", () => {
  it("asks for input when submitted empty", async () => {
    const user = userEvent.setup();
    render(<CheckVideoCard />);

    await user.click(screen.getByRole("button", { name: /check video/i }));

    expect(screen.getByText("Paste a YouTube link or video ID first.")).toBeInTheDocument();
    expect(screen.getByLabelText("YouTube link or video ID")).toHaveAttribute("aria-invalid", "true");
    expect(push).not.toHaveBeenCalled();
  });

  it("rejects input that is not a YouTube link or ID", async () => {
    const user = userEvent.setup();
    render(<CheckVideoCard />);

    await user.type(screen.getByLabelText("YouTube link or video ID"), "https://example.com{Enter}");

    expect(screen.getByText("That doesn’t look like a YouTube link or video ID.")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("goes to the video page for a valid link", async () => {
    const user = userEvent.setup();
    render(<CheckVideoCard />);

    await user.type(
      screen.getByLabelText("YouTube link or video ID"),
      "https://youtu.be/dQw4w9WgXcQ{Enter}",
    );

    expect(push).toHaveBeenCalledWith("/video?id=dQw4w9WgXcQ");
  });

  it("shows the info text on click and hides it on Escape", async () => {
    const user = userEvent.setup();
    render(<CheckVideoCard />);
    const info = screen.getByRole("button", { name: "More about checking a video" });
    const text = screen.getByText("Works best with children’s videos up to 15 minutes.");

    expect(text).not.toBeVisible();
    await user.click(info);
    expect(info).toHaveAttribute("aria-expanded", "true");
    expect(text).toBeVisible();
    await user.unhover(info);
    expect(text).toBeVisible(); // stays open after a click
    await user.keyboard("{Escape}");
    expect(text).not.toBeVisible();
  });

  it("shows the info text while the mouse hovers", async () => {
    const user = userEvent.setup();
    render(<CheckVideoCard />);
    const info = screen.getByRole("button", { name: "More about checking a video" });
    const text = screen.getByText("Works best with children’s videos up to 15 minutes.");

    await user.hover(info);
    expect(text).toBeVisible();
    await user.unhover(info);
    expect(text).not.toBeVisible();
  });

  it("describes the input with the info text even while it is closed", () => {
    render(<CheckVideoCard />);
    expect(screen.getByLabelText("YouTube link or video ID")).toHaveAccessibleDescription(
      /Works best with children’s videos up to 15 minutes\./,
    );
  });
});
