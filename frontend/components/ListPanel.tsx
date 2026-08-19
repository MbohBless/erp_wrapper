import Blueprint from "@/components/Blueprint";

export type ListRow = {
  title: string;
  meta: string;
  value: string;
  valueClass?: string; // e.g. "text-err"
  tag?: { text: string; className: string };
};

export default function ListPanel({
  title,
  dotColor,
  rows,
  action,
  emptyText = "Nothing to show.",
}: {
  title: string;
  dotColor: string; // css color
  rows: ListRow[];
  action?: string;
  /** Shown instead of rows when there is genuinely no data. */
  emptyText?: string;
}) {
  return (
    <Blueprint className="p-0 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-divider">
        <div className="flex items-center gap-2.5">
          <span className="w-2 h-2" style={{ background: dotColor }} />
          <span className="font-heading font-semibold text-base">{title}</span>
        </div>
        {action && <span className="text-xs text-accent cursor-pointer">{action}</span>}
      </div>
      <div>
        {rows.length === 0 && (
          <div className="px-5 py-10 text-center muted-2 text-sm">{emptyText}</div>
        )}
        {rows.map((row, i) => (
          <div
            key={i}
            className={`flex items-center justify-between px-5 py-3 ${
              i < rows.length - 1 ? "border-b border-solid divide-soft" : ""
            }`}
          >
            <div>
              <div className="text-sm font-medium">{row.title}</div>
              <div className="text-xs muted">{row.meta}</div>
            </div>
            {row.tag ? (
              <span className={`text-[11px] px-2.5 py-0.5 rounded-full ${row.tag.className}`}>
                {row.tag.text}
              </span>
            ) : (
              <span
                className={`font-heading font-semibold text-[15px] ${row.valueClass ?? ""}`}
              >
                {row.value}
              </span>
            )}
          </div>
        ))}
      </div>
    </Blueprint>
  );
}
