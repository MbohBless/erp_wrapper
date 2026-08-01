"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Measure a container's width in CSS pixels.
 *
 * Charts render at real pixel dimensions rather than with a scaled viewBox:
 * `preserveAspectRatio="none"` stretches strokes and corner radii unevenly, so
 * a 2px line reads as 3px on one axis and 1px on the other. Measuring instead
 * keeps mark geometry honest and makes pointer maths a straight lookup.
 */
export function useElementWidth<T extends HTMLElement>(fallback = 640) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new ResizeObserver((entries) => {
      const next = entries[0]?.contentRect.width;
      if (next && next > 0) setWidth(Math.round(next));
    });
    observer.observe(node);
    setWidth(Math.round(node.getBoundingClientRect().width) || fallback);
    return () => observer.disconnect();
  }, [fallback]);

  return { ref, width };
}
