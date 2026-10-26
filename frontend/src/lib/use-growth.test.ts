import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getMeta, type Meta } from "./api";
import { POLL_MS, useGrowth } from "./use-growth";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  getMeta: vi.fn(),
}));

const meta = (videoCount: number, channelCount: number, changes: Partial<Meta> = {}): Meta => ({
  videoCount,
  channelCount,
  updatedAt: "2026-10-26",
  addedLast7Days: 1043,
  channelCount7DaysAgo: 540,
  lastAddedAt: "2026-10-26T10:00:00Z",
  referenceCount: 16375,
  channelsCheckedAt: null,
  ...changes,
});

let visibility: DocumentVisibilityState = "visible";

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  visibility = "visible";
  vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visibility);
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

async function poll() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(POLL_MS);
  });
}

describe("useGrowth", () => {
  it("starts the count-up from a week ago", async () => {
    vi.mocked(getMeta).mockResolvedValue(meta(16402, 542));
    const { result } = renderHook(() => useGrowth());
    expect(result.current).toBe("loading");
    await waitFor(() => expect(result.current).not.toBe("loading"));
    expect(result.current).toEqual({
      videos: 16402,
      channels: 542,
      pastWeek: 1043,
      from: { videos: 15359, channels: 540, pastWeek: 0 },
    });
  });

  it("only goes up while the page is open, and the past week grows with it", async () => {
    vi.mocked(getMeta).mockResolvedValueOnce(meta(16402, 542));
    const { result } = renderHook(() => useGrowth());
    await waitFor(() => expect(result.current).not.toBe("loading"));
    vi.mocked(getMeta).mockResolvedValueOnce(meta(16405, 543, { addedLast7Days: 900 }));
    await poll();
    expect(result.current).toMatchObject({ videos: 16405, channels: 543, pastWeek: 1046 });
    // A video taken out, or the week moving on, waits for the next page load.
    vi.mocked(getMeta).mockResolvedValueOnce(meta(16400, 542, { addedLast7Days: 10 }));
    await poll();
    expect(result.current).toMatchObject({ videos: 16405, channels: 543, pastWeek: 1046 });
  });

  it("asks only while the tab is visible", async () => {
    vi.mocked(getMeta).mockResolvedValue(meta(16402, 542));
    renderHook(() => useGrowth());
    await waitFor(() => expect(getMeta).toHaveBeenCalledTimes(1));
    visibility = "hidden";
    await poll();
    expect(getMeta).toHaveBeenCalledTimes(1);
    visibility = "visible";
    await poll();
    expect(getMeta).toHaveBeenCalledTimes(2);
  });

  it("says so if the first request fails, and keeps its numbers if a later one does", async () => {
    vi.mocked(getMeta).mockRejectedValueOnce(new Error("offline"));
    const failed = renderHook(() => useGrowth());
    await act(async () => {
      await Promise.resolve();
    });
    expect(failed.result.current).toBe("failed");
    vi.mocked(getMeta).mockResolvedValueOnce(meta(16402, 542)).mockRejectedValueOnce(new Error("offline"));
    const { result } = renderHook(() => useGrowth());
    await waitFor(() => expect(result.current).not.toBe("loading"));
    await poll();
    expect(result.current).toMatchObject({ videos: 16402 });
  });
});
