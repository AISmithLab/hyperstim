// The rankings page's state, kept in the URL (plan 007): /rankings?view=…&sort=…&order=…&category=…&q=…&page=…
import type { Order, SortKey } from "@/lib/api";
import { categoryLabel } from "@/lib/categories";
import { FEATURE_INFO } from "@/lib/features";

export type View = "videos" | "channels";

export type RankingState = {
  view: View;
  /** "score" or a feature key. */
  sort: SortKey;
  order: Order;
  /** Category key; "" = all. */
  category: string;
  /** Search text, trimmed; "" = none. */
  q: string;
  /** From 1. */
  page: number;
};

export const DEFAULT_STATE: RankingState = {
  view: "videos",
  sort: "score",
  order: "desc",
  category: "",
  q: "",
  page: 1,
};

export const PAGE_SIZE = 25;
export const MAX_QUERY = 100;

/** The state in a URL's query; anything invalid falls back to its default. */
export function parseState(params: URLSearchParams): RankingState {
  const view = params.get("view");
  const sort = params.get("sort") ?? "";
  const category = params.get("category") ?? "";
  const page = Number(params.get("page"));
  return {
    view: view === "channels" ? "channels" : "videos",
    sort: Object.hasOwn(FEATURE_INFO, sort) ? sort : "score",
    order: params.get("order") === "asc" ? "asc" : "desc",
    category: categoryLabel(category) ? category : "",
    q: (params.get("q") ?? "").trim().slice(0, MAX_QUERY),
    page: Number.isInteger(page) && page > 1 ? page : 1,
  };
}

/** The state as a query string, defaults left out ("" when all are defaults). */
export function serializeState(state: RankingState): string {
  const params = new URLSearchParams();
  for (const key of Object.keys(DEFAULT_STATE) as (keyof RankingState)[]) {
    if (state[key] !== DEFAULT_STATE[key]) params.set(key, String(state[key]));
  }
  return params.toString();
}

/**
 * The page buttons to show: all of them up to 9 pages, else the first, the last and the current
 * one with two either side, with gaps; always 9 slots, so the control keeps its width.
 */
export function pageWindow(page: number, count: number): (number | "gap")[] {
  const range = (from: number, to: number) => Array.from({ length: to - from + 1 }, (_, i) => from + i);
  if (count <= 9) return range(1, count);
  if (page <= 5) return [...range(1, 7), "gap", count];
  if (page >= count - 4) return [1, "gap", ...range(count - 6, count)];
  return [1, "gap", ...range(page - 2, page + 2), "gap", count];
}
