"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Small circled "i" that shows `children` in a speech bubble on mouse hover, click/tap, or
 * Enter/Space. The bubble opens leftwards, so place it at the right end of a row.
 */
export default function InfoTip({
  id,
  label,
  children,
  className = "",
}: {
  id: string;
  label: string;
  children: ReactNode;
  className?: string;
}) {
  // Hover shows it while the mouse is over; a click pins it until clicked again,
  // Escape, or a click outside.
  const [hovered, setHovered] = useState(false);
  const [pinned, setPinned] = useState(false);
  const open = hovered || pinned;
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = () => {
      setHovered(false);
      setPinned(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    const onPointer = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) close();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  return (
    <div
      ref={ref}
      // -mr-3: the 44px touch target overhangs so the visible circle lines up with the form's right edge.
      className={`relative -mr-3 ${className}`}
      // Hover only for mice; touch gets the click toggle alone.
      onPointerEnter={(e) => e.pointerType === "mouse" && setHovered(true)}
      onPointerLeave={(e) => e.pointerType === "mouse" && setHovered(false)}
    >
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setPinned((p) => !p)}
        className="flex size-11 items-center justify-center rounded-full"
      >
        <span
          aria-hidden="true"
          className="flex size-5 items-center justify-center rounded-full border-2 border-navy font-hand text-xs font-semibold leading-none text-navy"
        >
          i
        </span>
      </button>
      <div
        id={id}
        hidden={!open}
        className="absolute top-full -right-1 z-10 mt-2 w-64 text-left font-normal max-w-[calc(100vw-2.5rem)] -rotate-1 rounded-2xl border-2 border-navy bg-white p-4 text-sm shadow-md before:absolute before:-top-[9px] before:right-[18px] before:size-4 before:rotate-45 before:border-t-2 before:border-l-2 before:border-navy before:bg-white"
      >
        {children}
      </div>
    </div>
  );
}
