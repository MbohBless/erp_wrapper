"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Icon } from "@/components/icons";
import { useBranding } from "@/lib/branding";
import { useI18n } from "@/lib/i18n";
import { canSee, useRole } from "@/lib/role";
import { useTheme } from "@/lib/theme";

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
  mobileOpen = false,
  onClose,
}: {
  collapsed: boolean;
  user: string | null;
  onLogout: () => void;
  /** Mobile only: the sidebar is a slide-over there, not a column. */
  mobileOpen?: boolean;
  onClose?: () => void;
}) {
  const pathname = usePathname();
  const { t } = useI18n();
  const { role } = useRole();
  // The API refuses these routes anyway; this stops the menu advertising pages
  // that would only answer 403. A group whose items all disappear is dropped
  // too, so no orphaned section heading is left behind.
  const visibleGroups = GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((i) => canSee(i.key, role)),
  })).filter((g) => g.items.length > 0);
  // Close the slide-over once a destination is chosen — otherwise it stays
  // over the page the user just navigated to.
  useEffect(() => {
    onClose?.();
    // Only the route matters here; including onClose would re-close on every
    // parent render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose?.();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mobileOpen, onClose]);

  const { branding } = useBranding();
  const { theme } = useTheme();
  const width = collapsed ? "md:w-20" : "md:w-[280px]";
  const initials = (user ?? "AM").slice(0, 2).toUpperCase();
  // Prefer the variant matching the active theme; fall back to the other so a
  // tenant who uploaded only one logo still gets it.
  const logo =
    theme === "dark"
      ? branding.logo_dark_data_url || branding.logo_light_data_url
      : branding.logo_light_data_url || branding.logo_dark_data_url;

  return (
    <aside
      // Mobile: a fixed slide-over above the content. Desktop (md+): a static
      // column, as before. It used to be `hidden md:flex`, so on a phone there
      // was no navigation at all and the menu button toggled a width nobody
      // could see.
      className={`${width} w-[280px] fixed md:static inset-y-0 left-0 z-50 flex flex-col shrink-0 h-full border-r border-divider bg-bg transition-transform md:transition-[width] duration-200 ${
        mobileOpen ? "translate-x-0" : "-translate-x-full"
      } md:translate-x-0`}
      aria-hidden={!mobileOpen ? undefined : false}
    >
      {/* Brand — the tenant's logo and name when they have set one. */}
      <div className="h-[72px] shrink-0 flex items-center gap-3 px-5 border-b border-divider">
        {logo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={logo}
            alt={branding.app_name}
            className="w-[34px] h-[34px] rounded-lg shrink-0 object-contain"
          />
        ) : (
          <div className="w-[34px] h-[34px] rounded-lg shrink-0 grid place-items-center bg-accent text-bg">
            <Icon name="flask" size={20} sw={2} />
          </div>
        )}
        {!collapsed && (
          <div className="leading-none min-w-0">
            <div className="font-heading font-bold text-[19px] tracking-tight truncate">
              {branding.app_name}
            </div>
            <div className="text-[10px] tracking-[0.14em] uppercase muted mt-0.5 truncate">
              {branding.tagline || t("brand.tagline")}
            </div>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto eq-scroll px-3 py-3.5 flex flex-col gap-0.5">
        {visibleGroups.map((group) => (
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
                // next/link, not <a>. A plain anchor is a full document
                // navigation: the browser discards the page, refetches and
                // re-parses the bundle, remounts React and re-runs every
                // provider query — which is why changing tab looked like the
                // whole site reloading.
                <Link
                  key={item.key}
                  href={href}
                  prefetch={href !== "#"}
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
                </Link>
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
