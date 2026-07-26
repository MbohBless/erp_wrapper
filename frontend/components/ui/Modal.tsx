"use client";

import { type ReactNode, useEffect, useState } from "react";
import { createPortal } from "react-dom";

/** Centered modal with a click-to-dismiss backdrop. The panel is a blueprint card.
 *
 * Portalled to <body> so it centres on the viewport rather than inside a
 * transformed ancestor (e.g. `.eq-view`), which would otherwise contain it.
 */
export default function Modal({
  onClose,
  className = "max-w-[480px]",
  children,
}: {
  onClose: () => void;
  className?: string;
  children: ReactNode;
}) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!mounted) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[100] grid place-items-center p-4 bg-[color-mix(in_srgb,#0b1220_45%,transparent)]"
      onClick={onClose}
    >
      <div
        className={`m3-dialog w-full bg-bg ${className}`}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>,
    document.body
  );
}
