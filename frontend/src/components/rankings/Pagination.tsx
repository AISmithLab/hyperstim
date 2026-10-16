import { pageWindow } from "./state";

const STEP_BUTTON =
  "flex min-h-11 min-w-11 items-center justify-center gap-1 rounded-full border-2 border-navy px-3 font-semibold text-navy hover:bg-sky disabled:border-navy/20 disabled:text-navy/30 disabled:hover:bg-transparent sm:px-4";

/**
 * Page control (see STYLE.md, Page control): Previous, the page window and Next from `sm`;
 * ‹ Page 3 of 655 › below it.
 */
export default function Pagination({
  page,
  pageCount,
  onChange,
}: {
  page: number;
  pageCount: number;
  onChange: (page: number) => void;
}) {
  if (pageCount <= 1) return null;
  return (
    <nav aria-label="Pages" className="mt-6 flex items-center justify-center gap-2 sm:gap-3">
      <button
        type="button"
        aria-label="Previous page"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
        className={STEP_BUTTON}
      >
        <span aria-hidden="true">‹</span>
        <span className="hidden sm:inline">Previous</span>
      </button>
      <p className="px-2 text-sm text-ink sm:hidden">
        Page {page.toLocaleString("en-US")} of {pageCount.toLocaleString("en-US")}
      </p>
      <ul className="hidden items-center gap-1 sm:flex">
        {pageWindow(page, pageCount).map((item, i) =>
          item === "gap" ? (
            <li key={`gap${i}`} aria-hidden="true" className="w-6 text-center text-ink">
              …
            </li>
          ) : (
            <li key={item}>
              <button
                type="button"
                aria-label={`Page ${item}`}
                aria-current={item === page ? "page" : undefined}
                onClick={() => onChange(item)}
                className="flex h-11 min-w-11 items-center justify-center rounded-full px-2 text-sm font-semibold text-navy tabular-nums hover:bg-sky aria-[current=page]:bg-sunny"
              >
                {item.toLocaleString("en-US")}
              </button>
            </li>
          ),
        )}
      </ul>
      <button
        type="button"
        aria-label="Next page"
        disabled={page >= pageCount}
        onClick={() => onChange(page + 1)}
        className={STEP_BUTTON}
      >
        <span className="hidden sm:inline">Next</span>
        <span aria-hidden="true">›</span>
      </button>
    </nav>
  );
}
