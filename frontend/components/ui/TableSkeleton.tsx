/** Placeholder rows shown while a table's data loads. */
export default function TableSkeleton({ cols, rows = 6 }: { cols: number; rows?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <tr key={i} className="border-b border-solid divide-soft">
          <td colSpan={cols} className="px-5 py-3">
            <div className="h-4 rounded bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)] animate-pulse" />
          </td>
        </tr>
      ))}
    </>
  );
}
