import { describe, expect, it } from "vitest";
import { DEFAULT_STATE, pageWindow, parseState, serializeState } from "./state";

describe("parseState", () => {
  it("reads every field", () => {
    const params = new URLSearchParams(
      "view=channels&sort=cuts_per_min&order=asc&category=play&q=%20zippy%20&page=3",
    );
    expect(parseState(params)).toEqual({
      view: "channels",
      sort: "cuts_per_min",
      order: "asc",
      category: "play",
      q: "zippy",
      page: 3,
    });
  });

  it("falls back to the defaults for missing or invalid values", () => {
    expect(parseState(new URLSearchParams())).toEqual(DEFAULT_STATE);
    const params = new URLSearchParams("view=x&sort=toString&order=up&category=sports&page=-2");
    expect(parseState(params)).toEqual(DEFAULT_STATE);
    expect(parseState(new URLSearchParams("page=2.5")).page).toBe(1);
  });

  it("cuts the search to 100 characters", () => {
    expect(parseState(new URLSearchParams({ q: "a".repeat(150) })).q).toHaveLength(100);
  });
});

describe("serializeState", () => {
  it("leaves out defaults", () => {
    expect(serializeState(DEFAULT_STATE)).toBe("");
    expect(serializeState({ ...DEFAULT_STATE, view: "channels", page: 2 })).toBe("view=channels&page=2");
  });

  it("round-trips", () => {
    const state = { view: "channels", sort: "lufs", order: "asc", category: "music", q: "café & co", page: 4 } as const;
    expect(parseState(new URLSearchParams(serializeState(state)))).toEqual(state);
  });
});

describe("pageWindow", () => {
  it("shows every page up to 9", () => {
    expect(pageWindow(1, 1)).toEqual([1]);
    expect(pageWindow(4, 9)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9]);
  });

  it("keeps 9 slots with gaps", () => {
    expect(pageWindow(1, 655)).toEqual([1, 2, 3, 4, 5, 6, 7, "gap", 655]);
    expect(pageWindow(5, 655)).toEqual([1, 2, 3, 4, 5, 6, 7, "gap", 655]);
    expect(pageWindow(6, 655)).toEqual([1, "gap", 4, 5, 6, 7, 8, "gap", 655]);
    expect(pageWindow(651, 655)).toEqual([1, "gap", 649, 650, 651, 652, 653, 654, 655]);
    expect(pageWindow(650, 655)).toEqual([1, "gap", 648, 649, 650, 651, 652, "gap", 655]);
  });
});
