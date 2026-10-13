"use client";

import { useCallback, useEffect, useState } from "react";

export type ApiState<T> =
  | { status: "loading" }
  | { status: "error"; error: unknown }
  | { status: "success"; data: T };

/** Runs `load` on mount; `retry` runs it again. `load` must be stable (module-level or memoized). */
export function useApi<T>(load: () => Promise<T>): ApiState<T> & { retry: () => void } {
  const [state, setState] = useState<ApiState<T>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let current = true;
    load().then(
      (data) => current && setState({ status: "success", data }),
      (error: unknown) => current && setState({ status: "error", error }),
    );
    return () => {
      current = false;
    };
  }, [load, attempt]);

  const retry = useCallback(() => {
    setState({ status: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  return { ...state, retry };
}
