import type { ReactNode } from "react";

/** Hairline card frame with corner registration ticks (EquiMed "blueprint"). */
export default function Blueprint({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`blueprint ${className}`}>
      {children}
      <i className="corner corner-tl" />
      <i className="corner corner-tr" />
      <i className="corner corner-bl" />
      <i className="corner corner-br" />
    </div>
  );
}
