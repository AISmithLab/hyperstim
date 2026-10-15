import { FEATURE_GROUPS, FEATURE_INFO } from "@/lib/features";
import type { Measure } from "./chart";

/**
 * Picks what the over-years chart shows, one at a time (see STYLE.md, Measurement picker):
 * chips in the measurement table's groups when `wide`, a native select on phones.
 */
export default function MeasurementPicker({
  value,
  onChange,
  wide,
}: {
  value: Measure;
  onChange: (measure: Measure) => void;
  wide: boolean;
}) {
  if (!wide) {
    return (
      <label className="mt-4 block">
        <span className="text-sm font-semibold text-navy">Show</span>
        <span className="relative mt-1 block">
          <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="h-12 w-full appearance-none rounded-full border-2 border-navy bg-white pr-11 pl-5 text-navy focus:shadow-[0_0_0_5px_var(--color-sunny)] focus:outline-none"
          >
            <option value="overall">Overall</option>
            {FEATURE_GROUPS.map((group) => (
              <optgroup key={group.title} label={group.title}>
                {group.keys.map((key) => (
                  <option key={key} value={key}>
                    {FEATURE_INFO[key].name}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            className="pointer-events-none absolute top-1/2 right-5 size-4 -translate-y-1/2"
          >
            <path d="M4.5 7.5 10 13l5.5-5.5" fill="none" strokeWidth="2.5" className="stroke-navy" />
          </svg>
        </span>
      </label>
    );
  }

  const chip = (measure: Measure, name: string) => (
    <button
      key={measure}
      type="button"
      aria-pressed={measure === value}
      onClick={() => onChange(measure)}
      className="group flex min-h-11 items-center rounded-full text-sm font-semibold text-navy"
    >
      <span className="rounded-full border border-navy/15 px-3 py-1.5 group-hover:bg-sky group-aria-pressed:border-sunny group-aria-pressed:bg-sunny">
        {name}
      </span>
    </button>
  );
  return (
    <div role="group" aria-label="Show" className="mt-3">
      <div className="flex flex-wrap gap-x-1.5">{chip("overall", "Overall")}</div>
      {FEATURE_GROUPS.map((group) => (
        <div key={group.title} className="flex flex-wrap items-center gap-x-1.5">
          <span className="mr-1.5 text-sm text-ink">{group.title}</span>
          {group.keys.map((key) => chip(key, FEATURE_INFO[key].name))}
        </div>
      ))}
    </div>
  );
}
