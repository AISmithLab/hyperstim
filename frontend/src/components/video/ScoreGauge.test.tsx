import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ScoreGauge, { needleAngle } from "./ScoreGauge";

function mockReducedMotion(reduce: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: reduce, media: query }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("needleAngle", () => {
  it.each([
    [0, 0],
    [50, 90],
    [100, 180],
    [-5, 0],
    [120, 180],
  ])("points %i at %i°", (score, angle) => {
    expect(needleAngle(score)).toBe(angle);
  });
});

describe("ScoreGauge", () => {
  it("reads one value to screen readers", () => {
    mockReducedMotion(true);
    render(<ScoreGauge score={86.6} />);
    expect(screen.getByText("Stimulation score 87 out of 100")).toBeInTheDocument();
    expect(screen.getByText("87")).toHaveAttribute("aria-hidden", "true");
  });

  it("shows the final value at once with reduced motion", () => {
    mockReducedMotion(true);
    const { container } = render(<ScoreGauge score={50} />);
    expect(screen.getByText("50")).toBeInTheDocument();
    expect(container.querySelector("svg")).toHaveAttribute("data-angle", "90");
  });

  it("sweeps from 0 to the score", () => {
    vi.useFakeTimers({ toFake: ["requestAnimationFrame", "cancelAnimationFrame", "performance"] });
    mockReducedMotion(false);
    const { container } = render(<ScoreGauge score={50} />);
    expect(screen.getByText("0")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1100));
    expect(screen.getByText("50")).toBeInTheDocument();
    expect(container.querySelector("svg")).toHaveAttribute("data-angle", "90");
  });
});
