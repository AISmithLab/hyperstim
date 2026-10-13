import InfoTip from "@/components/InfoTip";
import ScoreMeter from "@/components/ScoreMeter";
import type { Feature } from "@/lib/api";
import { FEATURE_GROUPS, FEATURE_INFO, featureDisplay, formatValue } from "@/lib/features";

/** The 12 measurements in their three groups (see STYLE.md, Measurement table). */
export default function Measurements({ features }: { features: Feature[] }) {
  const byKey = new Map(features.map((f) => [f.key, f]));
  const [pacing, ...rest] = FEATURE_GROUPS;
  const group = ({ title, keys }: (typeof FEATURE_GROUPS)[number]) => (
    <Group key={title} title={title} features={keys.flatMap((k) => byKey.get(k) ?? [])} />
  );
  // Pacing on the left; the two shorter groups stacked on the right.
  return (
    <div className="grid gap-6 md:grid-cols-2 md:gap-x-6">
      {group(pacing)}
      <div className="grid content-start gap-6">{rest.map(group)}</div>
    </div>
  );
}

function Group({ title, features }: { title: string; features: Feature[] }) {
  const id = `group-${title.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <section aria-labelledby={id}>
      <h3 id={id} className="font-hand text-lg font-semibold text-navy">
        {title}
      </h3>
      <ul className="mt-1">
        {features.map((f) => (
          <Row key={f.key} feature={f} />
        ))}
      </ul>
    </section>
  );
}

function Row({ feature }: { feature: Feature }) {
  const info = FEATURE_INFO[feature.key];
  const display = featureDisplay(feature);
  const value = display.kind === "percentile" ? formatValue(feature.key, feature.value) : null;
  return (
    <li className="relative flex min-h-11 items-center justify-between gap-2 border-b border-navy/10 last:border-0">
      <span className="flex min-w-0 items-center">
        <span className="font-semibold text-navy">{info.name}</span>
        <InfoTip id={`feature-${feature.key}`} label={`About ${info.name}`} align="row" className="-my-1 shrink-0">
          <p>{info.description}</p>
          {value && (
            <p className="mt-2">
              <span className="font-semibold text-navy">This video:</span> {value}
            </p>
          )}
        </InfoTip>
      </span>
      <span className="w-28 shrink-0 text-right">
        {display.kind === "percentile" ? (
          <ScoreMeter
            score={display.percentile}
            size="compact"
            srLabel={`Higher than ${Math.round(display.percentile)}% of videos in our dataset`}
          />
        ) : (
          <span className="text-sm text-ink/80">{display.text}</span>
        )}
      </span>
    </li>
  );
}
