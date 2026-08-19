"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";

import { DOC_FIELD } from "@/components/ui/DocFormShell";

export type ComboOption = {
  /** The value stored on the form. */
  value: string;
  /** Optional second line — a serial's item name, a customer's town. */
  hint?: string | null;
};

/**
 * A text input that also offers what already exists.
 *
 * Deliberately *not* a `<select>`. These fields reference records that may not
 * be on file yet — an engineer visiting a customer that was never entered, a
 * serial number from a batch nobody has registered. A select forces the user to
 * create the master record first, mid-task; a plain input makes them retype
 * something the system already knows and invites typos that split one customer
 * into three.
 *
 * So: type freely, and matching records are offered. Picking one fills the exact
 * stored value; ignoring the list is always allowed.
 *
 * `options` failing to load is not an error state. The list is an aid, and the
 * field still works without it — which matters because whether the caller may
 * read the underlying list depends on their role.
 */
export default function Combobox({
  value,
  onChange,
  options,
  placeholder,
  required,
  emptyHint,
  id,
}: {
  value: string;
  onChange: (v: string) => void;
  options: ComboOption[];
  placeholder?: string;
  required?: boolean;
  /** Shown when nothing matches — tells the user free text is fine. */
  emptyHint?: string;
  id?: string;
}) {
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  const matches = useMemo(() => {
    const q = value.trim().toLowerCase();
    const pool = q
      ? options.filter(
          (o) =>
            o.value.toLowerCase().includes(q) ||
            (o.hint ?? "").toLowerCase().includes(q)
        )
      : options;
    return pool.slice(0, 8);
  }, [options, value]);

  // Close on outside click and on Escape, so the list never strands over the
  // rest of the form.
  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => setHighlight(0), [value]);

  const choose = (v: string) => {
    onChange(v);
    setOpen(false);
  };

  return (
    <div className="relative" ref={wrapRef}>
      <input
        id={id}
        className={DOC_FIELD}
        value={value}
        placeholder={placeholder}
        required={required}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            setOpen(false);
            return;
          }
          if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
            setOpen(true);
            return;
          }
          if (!matches.length) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setHighlight((h) => (h + 1) % matches.length);
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setHighlight((h) => (h - 1 + matches.length) % matches.length);
          } else if (e.key === "Enter" && open) {
            // Only intercept Enter while a suggestion is highlighted, so typing
            // a new value and submitting still works.
            e.preventDefault();
            choose(matches[highlight].value);
          }
        }}
      />

      {open && (matches.length > 0 || emptyHint) && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-40 left-0 right-0 mt-1 max-h-64 overflow-y-auto eq-scroll rounded-xl border border-divider bg-bg shadow-[var(--shadow-lg)] p-1.5"
        >
          {matches.map((o, i) => (
            <li key={o.value} role="option" aria-selected={i === highlight}>
              <button
                type="button"
                // mousedown, not click: the input's blur would close the list
                // before a click ever lands.
                onMouseDown={(e) => {
                  e.preventDefault();
                  choose(o.value);
                }}
                onMouseEnter={() => setHighlight(i)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm ${
                  i === highlight
                    ? "bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)]"
                    : ""
                }`}
              >
                <span className="block truncate">{o.value}</span>
                {o.hint && (
                  <span className="block text-[12px] muted truncate">{o.hint}</span>
                )}
              </button>
            </li>
          ))}
          {matches.length === 0 && emptyHint && (
            <li className="px-3 py-2 text-[12px] muted">{emptyHint}</li>
          )}
        </ul>
      )}
    </div>
  );
}
