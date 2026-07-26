import Blueprint from "@/components/Blueprint";
import type { ActivityItem } from "@/lib/api";
import { shortDate, xafCompact } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function RecentSales({ items }: { items: ActivityItem[] }) {
  const { t } = useI18n();
  const sales = items.filter((i) => i.type === "Sales Invoice").slice(0, 6);

  return (
    <Blueprint className="p-0 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-divider">
        <span className="font-heading font-semibold text-base">{t("dashboard.recentSales")}</span>
        <span className="text-xs text-accent cursor-pointer">{t("dashboard.viewAll")}</span>
      </div>

      {sales.length === 0 ? (
        <div className="py-12 text-center muted-2 text-sm">{t("dashboard.noSales")}</div>
      ) : (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="muted">
              <th className="text-left text-[11px] tracking-[0.08em] uppercase font-semibold px-5 py-2.5 border-b border-divider">
                {t("dashboard.col.account")}
              </th>
              <th className="text-left text-[11px] tracking-[0.08em] uppercase font-semibold py-2.5 border-b border-divider">
                {t("dashboard.col.invoice")}
              </th>
              <th className="text-left text-[11px] tracking-[0.08em] uppercase font-semibold py-2.5 border-b border-divider">
                {t("dashboard.col.date")}
              </th>
              <th className="text-right text-[11px] tracking-[0.08em] uppercase font-semibold px-5 py-2.5 border-b border-divider">
                {t("dashboard.col.amount")}
              </th>
            </tr>
          </thead>
          <tbody>
            {sales.map((s) => (
              <tr key={s.reference} className="border-b border-solid divide-soft">
                <td className="px-5 py-2.5 font-medium">{s.party ?? "—"}</td>
                <td className="py-2.5 muted">{s.reference}</td>
                <td className="py-2.5 muted">{shortDate(s.date)}</td>
                <td className="px-5 py-2.5 text-right font-semibold">
                  {xafCompact(s.amount)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Blueprint>
  );
}
