import Blueprint from "@/components/Blueprint";
import { Icon } from "@/components/icons";
import type { ActivityItem } from "@/lib/api";
import { shortDate, xafCompact } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const ICON_FOR: Record<string, string> = {
  "Sales Invoice": "revenue",
  "Purchase Invoice": "check",
  Payment: "receivable",
};

export default function ActivityFeed({ items }: { items: ActivityItem[] }) {
  const { t } = useI18n();
  return (
    <Blueprint className="p-0 overflow-hidden">
      <div className="px-5 py-4 border-b border-divider">
        <span className="font-heading font-semibold text-base">{t("dashboard.activity")}</span>
      </div>
      <div className="py-1.5">
        {items.length === 0 ? (
          <div className="py-12 text-center muted-2 text-sm">{t("dashboard.nothingRecent")}</div>
        ) : (
          items.slice(0, 6).map((it) => (
            <div key={`${it.type}-${it.reference}`} className="flex gap-3 px-5 py-2.5">
              <span className="w-[26px] h-[26px] rounded-md shrink-0 grid place-items-center bg-[color-mix(in_srgb,var(--color-accent)_14%,transparent)] text-accent">
                <Icon name={ICON_FOR[it.type] ?? "check"} size={14} />
              </span>
              <div className="text-[13px] leading-[1.4]">
                {it.type} · {it.party ?? it.reference}
                <div className="text-[11px] muted-2">
                  {xafCompact(it.amount)} · {shortDate(it.date)}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </Blueprint>
  );
}
