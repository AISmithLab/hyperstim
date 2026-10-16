import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FEATURE_GROUPS, FEATURE_INFO, featureSlug } from "@/lib/features";
import { videoHref } from "@/lib/routes";
import HowItWorks from "./HowItWorks";
import { MARKERS } from "./WhatWeMeasure";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const KEYS = FEATURE_GROUPS.flatMap((g) => g.keys);

describe("HowItWorks", () => {
  it("has one H1 without a highlight, then steps 1–4 and the questions in order", () => {
    render(<HowItWorks />);
    const [h1] = screen.getAllByRole("heading", { level: 1 });
    expect(h1).toHaveTextContent("How it works");
    expect(h1.querySelector(".marker")).toBeNull();
    const names = [
      "Step 1: Paste a link",
      "Step 2: We measure 12 things",
      "Step 3: We compare it with our dataset",
      "Step 4: You get a score",
      "Common questions",
    ];
    expect(names.map((name) => screen.getByRole("heading", { level: 2, name }))).toEqual(
      screen.getAllByRole("heading", { level: 2 }),
    );
  });

  it("lists every measurement with its anchor, marker number, description, and timeline label", () => {
    const { container } = render(<HowItWorks />);
    expect(Object.keys(MARKERS).sort()).toEqual([...KEYS].sort());
    expect(new Set(Object.values(MARKERS)).size).toBe(12);
    for (const key of KEYS) {
      const item = container.querySelector(`#${featureSlug(key)}`);
      expect(item, key).not.toBeNull();
      expect(item).toHaveTextContent(`${MARKERS[key]}${FEATURE_INFO[key].name}`);
      expect(item).toHaveTextContent(FEATURE_INFO[key].description);
      expect(screen.getByText(FEATURE_INFO[key].label)).toBeInTheDocument();
    }
  });

  it("opens every common question", async () => {
    const user = userEvent.setup();
    const { container } = render(<HowItWorks />);
    const questions = container.querySelector("#questions")!;
    const items = within(questions as HTMLElement).getAllByRole("group");
    expect(items).toHaveLength(6);
    for (const item of items) {
      expect(item).not.toHaveAttribute("open");
      await user.click(item.querySelector("summary")!);
      expect(item).toHaveAttribute("open");
    }
  });

  it("checks a video from step 1, like the home page", async () => {
    const user = userEvent.setup();
    render(<HowItWorks />);
    const step = screen.getByRole("region", { name: "Step 1: Paste a link" });

    await user.type(within(step).getByLabelText("YouTube link or video ID"), "dQw4w9WgXcQ{Enter}");

    expect(push).toHaveBeenCalledWith(videoHref("dQw4w9WgXcQ"));
  });
});
