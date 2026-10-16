"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { ChartGrid, TimeAxis } from "@/components/channel/ChartAxes";
import {
  formatDate,
  LABELS,
  measureName,
  monotonePath,
  pointOf,
  pointText,
  smooth,
  timeScale,
  yearRange,
  type Measure,
} from "@/components/channel/chart";
import ScoreMeter from "@/components/ScoreMeter";
import type { ChannelDetail, ChannelVideo } from "@/lib/api";
import { videoHref } from "@/lib/routes";
import { useWidth } from "@/lib/use-layout";
import { Badge } from "./parts";
import type { Side } from "./state";

const CROSS = 4; // half the size of a "No cuts" ×
const CROSS_LIFT = 7; // the × sits this far above the 0 line
const SIZE = 4.5; // a dot's radius; B's squares are as wide
const SIDES: Side[] = ["a", "b"];

/** Each side's look: fill for dots, a darker shade for outlines and the trend line (A solid, B dashed). */
const LOOK: Record<Side, { fill: string; stroke: string; dash?: string }> = {
  a: { fill: "fill-side-a", stroke: "stroke-side-a-strong" },
  b: { fill: "fill-side-b", stroke: "stroke-side-b-strong", dash: "7 5" },
};

type Dot = { side: Side; video: ChannelVideo; kind: "value" | "na"; value: number; cx: number; cy: number };

/**
 * Two channels' videos over the years on one chart (see STYLE.md, Two-channel chart): A's
 * videos as round dots with a solid trend line, B's as squares with a dashed one. Hovering
 * (or tapping) a dot shows its video; clicking it opens the video's page.
 */
export default function CompareChart({
  channels,
  measure,
  wide,
}: {
  channels: Record<Side, ChannelDetail>;
  measure: Measure;
  wide: boolean;
}) {
  const box = useRef<HTMLDivElement>(null);
  const width = useWidth(box, 640);
  const router = useRouter();
  const [hovered, setHovered] = useState<string | null>(null);

  const ranges = SIDES.map((s) => yearRange(channels[s].videos));
  const scale = timeScale(width, wide, Math.min(ranges[0][0], ranges[1][0]), Math.max(ranges[0][1], ranges[1][1]));
  const { x, y, axisY } = scale;

  const dots: Dot[] = SIDES.flatMap((side) =>
    channels[side].videos.flatMap((video): Dot[] => {
      const point = pointOf(video, measure);
      if (point.kind === "missing") return [];
      const cx = x(video.publishedAt);
      if (point.kind === "value") return [{ side, video, kind: "value", value: point.value, cx, cy: y(point.value) }];
      return [{ side, video, kind: "na", value: 0, cx, cy: y(0) - CROSS_LIFT }];
    }),
  );
  const trends = SIDES.map((side) => {
    // A video the measurement doesn't apply to stays out.
    const valued = dots.filter((d) => d.side === side && d.kind !== "na");
    const trend = smooth(valued.map((d) => d.value));
    return { side, path: monotonePath(trend.map((v, i) => [valued[i].cx, y(v)])) };
  });

  const key = (d: Dot) => `${d.side}-${d.video.id}`;
  const active = dots.find((d) => key(d) === hovered);

  return (
    <div ref={box} className="relative mt-4" data-chart="">
      <svg aria-hidden="true" width={width} height={axisY + LABELS} className="block overflow-visible">
        <ChartGrid scale={scale} />
        <TimeAxis scale={scale} />
        {active && (
          <line x1={active.cx} x2={active.cx} y1={axisY} y2={active.cy} strokeDasharray="3 3" className="stroke-navy/50" />
        )}
        <g key={measure} className="motion-safe:animate-fade-in">
          {trends.map(
            ({ side, path }) =>
              path && (
                <path
                  key={side}
                  d={path}
                  fill="none"
                  strokeWidth={2.5}
                  strokeDasharray={LOOK[side].dash}
                  className={LOOK[side].stroke}
                  data-trend={side}
                />
              ),
          )}
          {dots.map((d) => (
            <Mark key={key(d)} dot={d} on={key(d) === hovered} />
          ))}
        </g>
        {/* Pointer targets, ~24 px; screen readers have the table next to the chart. */}
        {dots.map((d) => (
          <circle
            key={key(d)}
            cx={d.cx}
            cy={d.cy}
            r={12}
            fill="transparent"
            className="cursor-pointer"
            data-hit={key(d)}
            onPointerEnter={() => setHovered(key(d))}
            onPointerLeave={(e) => e.pointerType === "mouse" && setHovered(null)}
            onClick={() => router.push(videoHref(d.video.id))}
          />
        ))}
      </svg>
      {active && <Popover dot={active} channel={channels[active.side].name} measure={measure} width={width} />}
    </div>
  );
}

/** A video's mark: A a circle, B a square; a ring/outline on the 0 line for none detected; a × for no cuts. */
function Mark({ dot, on }: { dot: Dot; on: boolean }) {
  const look = LOOK[dot.side];
  const { cx, cy } = dot;
  if (dot.kind === "na") {
    const d = CROSS + (on ? 1.5 : 0);
    return (
      <path
        d={`M ${cx - d} ${cy - d} L ${cx + d} ${cy + d} M ${cx + d} ${cy - d} L ${cx - d} ${cy + d}`}
        strokeWidth={on ? 2.75 : 2}
        strokeLinecap="round"
        className={look.stroke}
        data-dot={dot.side}
      />
    );
  }
  const r = on ? 7 : SIZE;
  const className = `${look.fill} ${look.stroke}`;
  const strokeWidth = on ? 2 : 1.5;
  return dot.side === "a" ? (
    <circle cx={cx} cy={cy} r={r} strokeWidth={strokeWidth} className={className} data-dot="a" />
  ) : (
    <rect x={cx - r} y={cy - r} width={2 * r} height={2 * r} rx={1.5} strokeWidth={strokeWidth} className={className} data-dot="b" />
  );
}

const POPOVER_W = 256;

function Popover({ dot, channel, measure, width }: { dot: Dot; channel: string; measure: Measure; width: number }) {
  const left = Math.min(Math.max(dot.cx - POPOVER_W / 2, 0), Math.max(0, width - POPOVER_W));
  const below = dot.cy < 130;
  return (
    <div
      aria-hidden="true"
      data-popover=""
      style={below ? { left, top: dot.cy + 14 } : { left, bottom: `calc(100% - ${dot.cy - 14}px)` }}
      className="pointer-events-none absolute z-[100] w-64 max-w-full rounded-2xl border border-navy/15 bg-white px-4 py-3 text-sm text-ink shadow-[0_4px_16px_rgb(15_46_138/0.08)]"
    >
      <p className="flex items-center gap-2 font-semibold text-navy">
        <Badge side={dot.side} />
        <span className="truncate">{channel}</span>
      </p>
      <p className="mt-1 line-clamp-2 font-semibold text-navy">“{dot.video.title}”</p>
      <p className="mt-1">{formatDate(dot.video.publishedAt)}</p>
      {dot.kind === "value" ? (
        <p className="mt-1 flex items-center gap-1">
          {measureName(measure)}:
          <ScoreMeter score={dot.value} size="compact" />
        </p>
      ) : (
        <p className="mt-1">{pointText(pointOf(dot.video, measure))}</p>
      )}
    </div>
  );
}
