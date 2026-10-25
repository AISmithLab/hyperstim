import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ChannelDetail, ChannelVideo, Feature } from "@/lib/api";
import CompareChart from "./CompareChart";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const CUTS = "inter_cut_dssim_mean"; // no value: "No cuts", drawn as a ×
const LOUD = "lufs"; // no value: "No sound", left out

function video(id: string, publishedAt: string, score: number, features: Feature[] = []): ChannelVideo {
  return { id, title: `Title ${id}`, publishedAt, score, features };
}

function channel(name: string, videos: ChannelVideo[]): ChannelDetail {
  return { id: `UC${name}`, name, videoCount: videos.length, score: 50, features: [], videos };
}

const A = channel("Alpha", [
  video("a1", "2020-01-01", 95, [{ key: CUTS, value: 0.4, percentile: 80 }, { key: LOUD, value: null, percentile: null }]),
  video("a2", "2021-06-01", 50, [{ key: CUTS, value: null, percentile: null }]),
  video("a3", "2022-03-01", 10, [{ key: CUTS, value: 0.2, percentile: 30 }]),
  video("a4", "2023-03-01", 40), // CUTS not measured: left out
]);
const B = channel("Beta", [
  video("b1", "2019-05-01", 70, [{ key: CUTS, value: 0.3, percentile: 60 }]),
  video("b2", "2024-05-01", 20, [{ key: CUTS, value: null, percentile: null }]),
]);

function renderChart(measure = "overall", channels = { a: A, b: B }) {
  return render(<CompareChart channels={channels} measure={measure} wide={false} />);
}

const q = (c: HTMLElement, selector: string) => c.querySelector(selector);

describe("CompareChart", () => {
  it("draws A as circles and B as squares, with a trend only for 3+ values", () => {
    const { container } = renderChart();
    expect(container.querySelectorAll('circle[data-dot="a"]')).toHaveLength(4);
    expect(container.querySelectorAll('rect[data-dot="b"]')).toHaveLength(2);
    expect(q(container, '[data-trend="a"]')).toBeInTheDocument();
    expect(q(container, '[data-trend="b"]')).toBeNull();
  });

  it("draws a × for no cuts, outside the trend, and leaves out unmeasured videos", () => {
    const { container } = renderChart(CUTS);
    // A: two values, one ×, one not measured; B: one value, one ×.
    expect(container.querySelectorAll('circle[data-dot="a"]')).toHaveLength(2);
    expect(container.querySelectorAll('path[data-dot="a"]')).toHaveLength(1);
    expect(container.querySelectorAll('path[data-dot="b"]')).toHaveLength(1);
    expect(q(container, '[data-hit="a-a4"]')).toBeNull();
    // Only two values on A: no trend.
    expect(q(container, "[data-trend]")).toBeNull();
  });

  it("leaves out a measurement with no value that isn't “No cuts”", () => {
    const { container } = renderChart(LOUD);
    expect(container.querySelectorAll("[data-dot]")).toHaveLength(0);
  });

  it("shows a value's popover below a high dot and enlarges it", () => {
    const { container } = renderChart();
    fireEvent.pointerEnter(q(container, '[data-hit="a-a1"]')!, { pointerType: "mouse" });
    const popover = q(container, "[data-popover]") as HTMLElement;
    expect(popover).toHaveTextContent("Alpha");
    expect(popover).toHaveTextContent("“Title a1”");
    expect(popover).toHaveTextContent("Jan 1, 2020");
    expect(popover).toHaveTextContent("Overall:");
    expect(popover.style.top).not.toBe("");
    expect(q(container, 'circle[data-dot="a"][r="7"]')).toBeInTheDocument();
    expect(q(container, "line")).toBeInTheDocument();
  });

  it("shows a popover above a low dot, for B's squares too", () => {
    const { container } = renderChart();
    fireEvent.pointerEnter(q(container, '[data-hit="b-b2"]')!, { pointerType: "mouse" });
    const popover = q(container, "[data-popover]") as HTMLElement;
    expect(popover).toHaveTextContent("Beta");
    expect(popover.style.bottom).not.toBe("");
    expect(q(container, 'rect[data-dot="b"][width="14"]')).toBeInTheDocument();
  });

  it("shows “No cuts” in a ×'s popover and enlarges the ×", () => {
    const { container } = renderChart(CUTS);
    const before = q(container, 'path[data-dot="a"]')!.getAttribute("stroke-width");
    fireEvent.pointerEnter(q(container, '[data-hit="a-a2"]')!, { pointerType: "mouse" });
    expect(q(container, "[data-popover]")).toHaveTextContent("No cuts");
    expect(q(container, 'path[data-dot="a"]')!.getAttribute("stroke-width")).not.toBe(before);
  });

  it("hides the popover when the mouse leaves, but keeps it after a tap", () => {
    const { container } = renderChart();
    const hit = q(container, '[data-hit="a-a3"]')!;
    fireEvent.pointerEnter(hit, { pointerType: "touch" });
    fireEvent.pointerLeave(hit, { pointerType: "touch" });
    expect(q(container, "[data-popover]")).toBeInTheDocument();
    fireEvent.pointerEnter(hit, { pointerType: "mouse" });
    fireEvent.pointerLeave(hit, { pointerType: "mouse" });
    expect(q(container, "[data-popover]")).toBeNull();
  });

  it("opens the video's page on click", () => {
    const { container } = renderChart();
    fireEvent.click(q(container, '[data-hit="b-b1"]')!);
    expect(push).toHaveBeenCalledWith(expect.stringContaining("b1"));
  });
});
