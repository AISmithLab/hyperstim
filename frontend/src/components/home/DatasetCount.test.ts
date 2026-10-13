import { describe, expect, it } from "vitest";
import { formatCount } from "./DatasetCount";

describe("formatCount", () => {
  it.each([
    [10412, "10k+"],
    [10000, "10k+"],
    [9999, "9k+"],
    [1000, "1k+"],
    [999, "999"],
  ])("formats %i as %s", (count, text) => {
    expect(formatCount(count)).toBe(text);
  });
});
