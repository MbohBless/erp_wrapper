"use client";

import { useState, type ReactNode } from "react";

import { Icon } from "@/components/icons";

/** ERPNext-style "More options" toggle: hides non-essential fields until opened. */
export default function Disclosure({
  label = "More options",
  defaultOpen = false,
  children,
}: {
  label?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 text-[13px] font-medium text-accent my-2 hover:opacity-80"
      >
        <span className={`transition-transform duration-150 ${open ? "rotate-180" : ""}`}>
          <Icon name="chevronDown" size={16} />
        </span>
        {open ? "Hide extra fields" : label}
      </button>
      {open && children}
    </>
  );
}
