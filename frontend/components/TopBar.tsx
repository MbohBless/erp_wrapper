"use client";

import { useState } from "react";

import { Icon } from "@/components/icons";
import { useI18n } from "@/lib/i18n";
import { useTheme } from "@/lib/theme";

export default function TopBar({
  user,
  onToggleCollapse,
  onOpenNav,
  onLogout,
}: {
  user: string | null;
  onToggleCollapse: () => void;
  onOpenNav: () => void;
  onLogout: () => void;
}) {
  const { theme, toggle } = useTheme();
  const { t } = useI18n();
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const initials = (user ?? "AM").slice(0, 2).toUpperCase();

  return (
    <header className="h-[72px] shrink-0 flex items-center gap-2 md:gap-4 px-3 md:px-6 border-b border-divider bg-bg relative z-20">
      {/* Two buttons rather than one branching on viewport width: the mobile
          sidebar is a slide-over and the desktop one collapses, so the same
          control means different things. */}
      <button
        type="button"
        onClick={onOpenNav}
        aria-label="Open navigation"
        className="md:hidden icobtn grid place-items-center w-9 h-9 shrink-0 border border-divider muted"
      >
        <Icon name="menu" size={17} />
      </button>
      <button
        type="button"
        onClick={onToggleCollapse}
        title="Toggle sidebar"
        className="hidden md:grid icobtn place-items-center w-9 h-9 shrink-0 border border-divider muted"
      >
        <Icon name="menu" size={17} />
      </button>

      <div className="flex-1 max-w-[520px] mx-auto relative">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 muted-3">
          <Icon name="search" size={16} />
        </span>
        <input
          className="eq-field w-full h-10 pl-9 pr-3 md:pr-14 text-sm"
          placeholder={t("topbar.search")}
        />
        <kbd className="hidden md:block absolute right-2.5 top-1/2 -translate-y-1/2 text-[11px] muted-2 border border-divider px-1.5 rounded">
          ⌘K
        </kbd>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {/* Notifications */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setNotifOpen((v) => !v);
              setProfileOpen(false);
            }}
            title="Notifications"
            className="icobtn relative grid place-items-center w-[38px] h-[38px] border border-divider muted"
          >
            <Icon name="bell" size={18} />
            {/* No unread badge: there is no notification source yet, and a
                permanent red dot trains people to ignore it. */}
          </button>
          {notifOpen && (
            <div className="absolute top-[46px] right-0 w-[340px] bg-bg rounded-card border border-divider shadow-[var(--shadow-lg)] z-40 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3.5 border-b border-divider">
                <span className="font-heading font-semibold text-[15px]">
                  Notifications
                </span>
              </div>
              {/* There is no notification backend yet. This used to render three
                  invented alerts with fake timestamps, which is indistinguishable
                  from real activity to someone looking at their own workspace. */}
              <div className="px-4 py-10 text-center muted-2 text-[13px]">
                No notifications yet.
              </div>
            </div>
          )}
        </div>

        {/* Theme */}
        <button
          type="button"
          onClick={toggle}
          title="Toggle theme"
          className="icobtn grid place-items-center w-[38px] h-[38px] border border-divider muted"
        >
          <Icon name={theme === "dark" ? "sun" : "moon"} size={18} />
        </button>

        <div className="w-px h-[26px] bg-divider mx-1" />

        {/* Profile */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setProfileOpen((v) => !v);
              setNotifOpen(false);
            }}
            className="icobtn flex items-center gap-2 pl-1 pr-1.5 py-1"
          >
            <span className="w-8 h-8 rounded-lg grid place-items-center bg-accent text-bg font-heading font-semibold text-[13px]">
              {initials}
            </span>
            <span className="muted-3">
              <Icon name="chevronDown" size={15} />
            </span>
          </button>
          {profileOpen && (
            <div className="absolute top-[46px] right-0 w-[230px] bg-bg rounded-card border border-divider shadow-[var(--shadow-lg)] z-40 overflow-hidden">
              <div className="px-4 py-3.5 border-b border-divider">
                <div className="font-semibold text-sm truncate">{user}</div>
                <div className="text-xs muted truncate">{user}</div>
              </div>
              <div className="p-1.5">
                <button
                  type="button"
                  onClick={toggle}
                  className="navitem flex items-center justify-between w-full gap-2.5 px-3 py-2.5 text-[13px] rounded-lg"
                >
                  <span className="flex items-center gap-2.5">
                    <Icon name="moon" size={16} />
                    Theme
                  </span>
                  <span className="text-[11px] muted capitalize">{theme}</span>
                </button>
              </div>
              <div className="border-t border-divider p-1.5">
                <button
                  type="button"
                  onClick={onLogout}
                  className="navitem flex items-center w-full gap-2.5 px-3 py-2.5 text-[13px] rounded-lg text-err"
                >
                  <Icon name="logout" size={16} />
                  Log out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
