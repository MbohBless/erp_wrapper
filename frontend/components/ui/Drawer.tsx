import type { ReactNode } from "react";

import { Icon } from "@/components/icons";

/** Right-hand slide-over panel with header, scrollable body and optional footer. */
export default function Drawer({
  eyebrow,
  title,
  onClose,
  footer,
  width = "max-w-[440px]",
  children,
}: {
  eyebrow?: string;
  title: string;
  onClose: () => void;
  footer?: ReactNode;
  width?: string;
  children: ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-[color-mix(in_srgb,#000_45%,transparent)]"
      onClick={onClose}
    >
      <div
        className={`w-full ${width} h-full bg-bg border-l border-divider flex flex-col`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="h-[72px] shrink-0 flex items-center justify-between px-6 border-b border-divider">
          <div>
            {eyebrow && (
              <div className="text-[10px] tracking-[0.12em] uppercase text-accent">
                {eyebrow}
              </div>
            )}
            <div className="font-heading font-semibold text-lg leading-tight tracking-wide">
              {title}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="icobtn grid place-items-center w-9 h-9 border border-divider muted"
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
    </div>
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
