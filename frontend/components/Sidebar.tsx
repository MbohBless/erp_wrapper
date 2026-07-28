"use client";

import { usePathname } from "next/navigation";

import { Icon } from "@/components/icons";
import { useI18n } from "@/lib/i18n";

// Nav keys that map to real routes (others are placeholders for now).
const ROUTES: Record<string, string> = {
  dashboard: "/dashboard",
  sales: "/sales",
  purchases: "/purchases",
  customers: "/customers",
  suppliers: "/suppliers",
  products: "/products",
  inventory: "/inventory",
  equipment: "/equipment",
  maintenance: "/maintenance",
  finance: "/finance",
  budget: "/budget",
  reports: "/reports",
  settings: "/settings",
};

const GROUPS: { label: string; items: { key: string; label: string }[] }[] = [
  {
    label: "Overview",
    items: [
      { key: "dashboard", label: "Dashboard" },
      { key: "sales", label: "Sales" },
      { key: "purchases", label: "Purchases" },
    ],
  },
  {
    label: "Operations",
    items: [
      { key: "products", label: "Products" },
      { key: "inventory", label: "Inventory" },
      { key: "equipment", label: "Equipment" },
      { key: "maintenance", label: "Maintenance" },
    ],
  },
  {
    label: "Relationships",
    items: [
      { key: "customers", label: "Customers" },
      { key: "suppliers", label: "Suppliers" },
    ],
  },
  {
    label: "Business",
    items: [
      { key: "finance", label: "Finance" },
      { key: "budget", label: "Budget" },
      { key: "reports", label: "Reports" },
      { key: "settings", label: "Settings" },
    ],
  },
];

export default function Sidebar({
  collapsed,
  user,
  onLogout,
}: {
  collapsed: boolean;
  user: string | null;
  onLogout: () => void;
}) {
  const pathname = usePathname();
  const { t } = useI18n();
  const width = collapsed ? "w-20" : "w-[280px]";
  const initials = (user ?? "AM").slice(0, 2).toUpperCase();

  return (
    <aside
      className={`${width} hidden md:flex flex-col shrink-0 h-full border-r border-divider bg-bg transition-[width] duration-200`}
    >
      {/* Brand */}
      <div className="h-[72px] shrink-0 flex items-center gap-3 px-5 border-b border-divider">
        <div className="w-[34px] h-[34px] rounded-lg shrink-0 grid place-items-center bg-accent text-bg">
          <Icon name="flask" size={20} sw={2} />
        </div>
        {!collapsed && (
          <div className="leading-none">
            <div className="font-heading font-bold text-[19px] tracking-tight">
              EquiMed
            </div>
            <div className="text-[10px] tracking-[0.14em] uppercase muted mt-0.5">
              {t("brand.tagline")}
            </div>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto eq-scroll px-3 py-3.5 flex flex-col gap-0.5">
        {GROUPS.map((group) => (
          <div key={group.label}>
            {!collapsed && (
              <div className="text-[10px] tracking-[0.12em] uppercase muted-3 px-3.5 pt-3 pb-1.5">
                {t(`nav.group.${group.label.toLowerCase()}`)}
              </div>
            )}
            {group.items.map((item) => {
              const href = ROUTES[item.key] ?? "#";
              const active = href !== "#" && pathname.startsWith(href);
              return (
                <a
                  key={item.key}
                  href={href}
                  data-active={active}
                  className={`navitem relative flex items-center gap-3 w-full px-3.5 py-2.5 rounded-lg text-sm ${
                    collapsed ? "justify-center" : ""
                  }`}
                >
                  {active && (
                    <span className="absolute left-0 top-[7px] bottom-[7px] w-[3px] bg-accent" />
                  )}
                  <span
                    className={`flex shrink-0 ${active ? "text-accent" : ""}`}
                  >
                    <Icon name={item.key} />
                  </span>
                  {!collapsed && <span>{t(`nav.${item.key}`)}</span>}
                </a>
              );
            })}
          </div>
        ))}
      </nav>

      {/* User footer */}
      <div className="shrink-0 flex items-center gap-3 px-4 py-3.5 border-t border-divider">
        <div className="w-9 h-9 rounded-lg shrink-0 grid place-items-center font-heading font-semibold text-sm bg-[color-mix(in_srgb,var(--color-accent)_18%,transparent)] text-accent">
          {initials}
        </div>
        {!collapsed && (
          <>
            <div className="flex-1 min-w-0 leading-tight">
              <div className="text-[13px] font-semibold truncate">
                {user ?? t("user.fallback")}
              </div>
              <div className="text-[11px] muted truncate">
                {t("user.subtitle")}
              </div>
            </div>
            <button
              type="button"
              onClick={onLogout}
              title={t("action.logout")}
              className="icobtn grid place-items-center w-8 h-8 shrink-0 muted"
            >
              <Icon name="logout" size={17} />
            </button>
          </>
        )}
      </div>
    </aside>
  );
}
