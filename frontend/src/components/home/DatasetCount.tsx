"use client";

import { getMeta } from "@/lib/api";
import { useApi } from "@/lib/use-api";

/** Dataset size for the hero: "10k+", or "thousands of" until the count is known. */
export default function DatasetCount() {
  const meta = useApi(getMeta);
  if (meta.status !== "success") return <>thousands of</>;
  return <>{formatCount(meta.data.videoCount)}</>;
}

export function formatCount(count: number): string {
  return count >= 1000 ? `${Math.floor(count / 1000)}k+` : String(count);
}
