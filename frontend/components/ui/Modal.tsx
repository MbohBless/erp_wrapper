import type { ReactNode } from "react";

/** Centered modal with a click-to-dismiss backdrop. The panel is a blueprint card. */
export default function Modal({
  onClose,
  className = "max-w-[480px]",
  children,
}: {
  onClose: () => void;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-4 bg-[color-mix(in_srgb,#000_50%,transparent)]"
      onClick={onClose}
    >
      <div
        className={`blueprint w-full bg-bg ${className}`}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
