"use client";

import { useRef, useState } from "react";
import { ChartGrid, TimeAxis } from "@/components/channel/ChartAxes";
import {
  formatDate,
  LABELS,
  LEFT,
  measureName,
  monotonePath,
  placeThumbs,
  pointOf,
  pointText,
  smooth,
  stackShifts,
  timeScale,
  yearRange,
  type Measure,
} from "@/components/channel/chart";
import ScoreMeter from "@/components/ScoreMeter";
import { thumbnailUrl, type ChannelDetail, type ChannelVideo } from "@/lib/api";
import { useWidth } from "@/lib/use-layout";
import { Badge } from "./parts";
import type { Side } from "./state";

const CROSS = 4; // half the size of a "No cuts" ×
const CROSS_LIFT = 7; // the × sits this far above the 0 line
const SIZE = 4.5; // a dot's radius; B's squares are as wide
const SIDES: Side[] = ["a", "b"];
// Hanging thumbnails, as on the channel page (TimeChart).
const THUMB_W = 64;
const THUMB_H = 36;
const THUMB_GAP = 6;
const ROW_PITCH = 10;
const FOCUS_NUDGE = 8;
const FOCUS_OPEN = THUMB_H + 16;
const GROUP_GAP = 12; // between A's thumbnails and B's

/** Each side's look: fill for dots, a darker shade for outlines and the trend line (A solid, B dashed). */
const LOOK: Record<Side, { fill: string; stroke: string; line: string; dash?: string }> = {
  a: { fill: "fill-side-a", stroke: "stroke-side-a-strong", line: "stroke-side-a-strong/35" },
  b: { fill: "fill-side-b", stroke: "stroke-side-b-strong", line: "stroke-side-b-strong/35", dash: "7 5" },
};

type Dot = { side: Side; video: ChannelVideo; kind: "value" | "na"; value: number; cx: number; cy: number };

/** A video on the chart: its side and ID, as `a-<id>`. */
export const videoKey = (side: Side, id: string) => `${side}-${id}`;

/**
 * Two channels' videos over the years on one chart (see STYLE.md, Two-channel chart): A's
 * videos as round dots with a solid trend line, B's as squares with a dashed one. From `sm`
 * each video's thumbnail hangs under the axis, A's in the first group and B's in the second.
 * A mouse hovering a dot or thumbnail shows its video in a popover; a click or tap opens it
 * (`onOpen`), and the page shows it under the chart. `marked` is the opened video.
 */
export default function CompareChart({
  channels,
  measure,
  wide,
  marked,
  onOpen,
}: {
  channels: Record<Side, ChannelDetail>;
  measure: Measure;
  wide: boolean;
  marked: string | null;
  onOpen: (key: string) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const width = useWidth(box, 640);
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

  const key = (d: { side: Side; video: ChannelVideo }) => videoKey(d.side, d.video.id);
  const isOn = (k: string) => k === hovered || k === marked;

  // Thumbnails: one group per side, A's first, each stacked like the channel page's.
  const focusKey = hovered ?? marked;
  let groupTop = axisY + LABELS;
  const groups = wide
    ? SIDES.map((side) => {
        const videos = channels[side].videos;
        // Right of the y labels' gutter, which holds the group's badge.
        const placed = placeThumbs(videos.map((v) => x(v.publishedAt) - LEFT), width - LEFT, THUMB_W, THUMB_GAP).map(
          (t) => ({ ...t, left: t.left + LEFT }),
        );
        const rows = placed.reduce((n, t) => Math.max(n, t.row + 1), 0);
        const focus = videos.findIndex((v) => videoKey(side, v.id) === focusKey);
        const shifts = stackShifts(placed, focus === -1 ? null : focus, THUMB_W, FOCUS_NUDGE, FOCUS_OPEN);
        const top = groupTop;
        // Room for a stack to open below its last row, so nothing under it moves on hover.
        groupTop += (rows - 1) * ROW_PITCH + THUMB_H + FOCUS_OPEN + GROUP_GAP;
        return {
          side,
          rows,
          top,
          thumbs: videos.map((video, i) => ({
            side,
            video,
            cx: x(video.publishedAt),
            left: placed[i].left,
            row: placed[i].row,
            top: top + placed[i].row * ROW_PITCH + shifts[i].dy,
            front: shifts[i].front,
          })),
        };
      })
    : [];
  const thumbs = groups.flatMap((g) => g.thumbs);
  const height = wide ? groupTop - GROUP_GAP : axisY + LABELS;
  const active = dots.find((d) => key(d) === hovered);

  // The guide from the axis up to the hovered dot, else the opened one.
  const guide = active ?? dots.find((d) => key(d) === marked);

  // Mouse only: on touch screens a tap opens the video under the chart instead of a popover
  // under the finger.
  const hover = (k: string | null) => (e: React.PointerEvent) => {
    if (e.pointerType === "mouse") setHovered(k);
  };

  return (
    <div ref={box} className="relative mt-4" data-chart="">
      <svg aria-hidden="true" width={width} height={height} className="block overflow-visible">
        <ChartGrid scale={scale} />
        {/* Lines from each date down to its thumbnail, in its side's colour; the marked one on top. */}
        {[...thumbs]
          .sort((p, q) => Number(isOn(key(p))) - Number(isOn(key(q))))
          .map((t) => {
            const on = isOn(key(t));
            return (
              <line
                key={key(t)}
                x1={t.cx}
                y1={axisY}
                x2={t.left + THUMB_W / 2}
                y2={t.top + 2}
                strokeWidth={on ? 2 : 1}
                className={on ? LOOK[t.side].stroke : LOOK[t.side].line}
              />
            );
          })}
        <TimeAxis scale={scale} />
        {guide && (
          <line x1={guide.cx} x2={guide.cx} y1={axisY} y2={guide.cy} strokeDasharray="3 3" className="stroke-navy/50" />
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
            <Mark key={key(d)} dot={d} on={isOn(key(d))} />
          ))}
        </g>
        {/* Pointer targets, ~24 px; keyboard users have the thumbnails, screen readers the table. */}
        {dots.map((d) => (
          <circle
            key={key(d)}
            cx={d.cx}
            cy={d.cy}
            r={12}
            fill="transparent"
            className="cursor-pointer"
            data-hit={key(d)}
            onPointerEnter={hover(key(d))}
            onPointerLeave={hover(null)}
            onClick={() => onOpen(key(d))}
          />
        ))}
      </svg>

      {groups.map((g) => (
        <span key={g.side} aria-hidden="true" className="absolute left-0" style={{ top: g.top + 6 }}>
          <Badge side={g.side} decorative />
        </span>
      ))}
      {thumbs.map((t) => {
        const k = key(t);
        const on = isOn(k);
        const rows = groups.find((g) => g.side === t.side)!.rows;
        return (
          <button
            key={k}
            id={`thumb-${k}`}
            type="button"
            aria-label={`${t.side.toUpperCase()}: ${t.video.title}, ${formatDate(t.video.publishedAt)}`}
            aria-current={k === marked ? "true" : undefined}
            onClick={() => onOpen(k)}
            onPointerEnter={hover(k)}
            onPointerLeave={hover(null)}
            onFocus={() => setHovered(k)}
            onBlur={() => setHovered(null)}
            style={{ left: t.left, top: t.top, width: THUMB_W, height: THUMB_H, zIndex: t.front ? 2 * rows + 1 : t.row }}
            className={`absolute overflow-hidden rounded bg-navy/10 ring-2 transition-[top,scale] duration-200 ease-out motion-reduce:transition-none ${t.front ? "scale-108" : ""} ${on ? "ring-navy" : "ring-white"}`}
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- static export, no image optimization */}
            <img src={thumbnailUrl(t.video.id, "mq")} alt="" loading="lazy" width={THUMB_W} height={THUMB_H} className="size-full object-cover" />
          </button>
        );
      })}
      {active && <Popover dot={active} channel={channels[active.side].name} measure={measure} width={width} />}
    </div>
  );
}

/** A video's mark: A a circle, B a square; a × for no cuts. */
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
