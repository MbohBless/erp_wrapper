"use client";

import { type ReactNode, useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { Icon } from "@/components/icons";

/** Right-hand slide-over panel with header, scrollable body and optional footer.
 *
 * Rendered in a portal on <body> so it is anchored to the viewport (full height,
 * flush to the edge) regardless of any transformed ancestor such as `.eq-view`,
 * which would otherwise become the containing block for `position: fixed`.
 */
export default function Drawer({
  eyebrow,
  title,
  onClose,
  footer,
  width = "max-w-[460px]",
  children,
}: {
  eyebrow?: string;
  title: string;
  onClose: () => void;
  footer?: ReactNode;
  width?: string;
  children: ReactNode;
}) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose]);

  if (!mounted) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex justify-end bg-[color-mix(in_srgb,#0b1220_28%,transparent)]"
      onClick={onClose}
    >
      <div
        className={`w-full ${width} h-full bg-bg border-l border-divider flex flex-col shadow-[-24px_0_60px_-24px_rgba(0,0,0,0.35)] animate-[slideIn_0.2s_ease]`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="h-[72px] shrink-0 flex items-center justify-between px-6 border-b border-divider">
          <div className="min-w-0">
            {eyebrow && (
              <div className="text-[10px] tracking-[0.12em] uppercase text-accent">
                {eyebrow}
              </div>
            )}
            <div className="font-heading font-semibold text-lg leading-tight tracking-wide truncate">
              {title}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="icobtn grid place-items-center w-9 h-9 border border-divider muted shrink-0"
            title="Close"
          >
            <Icon name="close" size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto eq-scroll p-6">{children}</div>
        {footer && (
          <div className="shrink-0 p-4 border-t border-divider flex justify-end gap-2.5">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}

/** Label / value row used inside detail drawers. */
export function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 py-2.5 border-b border-solid divide-soft">
      <span className="text-sm muted">{label}</span>
      <span className="text-sm text-right">{value || "—"}</span>
    </div>
  );
}
