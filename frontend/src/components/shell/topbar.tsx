"use client";

import { Menu, Search } from "lucide-react";

import { BrandMark } from "@/components/shell/brand-mark";
import { NotificationCenter } from "@/components/notifications/notification-center";
import { LanguageSwitcher } from "@/components/shell/language-switcher";
import { OfflineIndicator } from "@/components/shell/offline-indicator";
import { AppSwitcher } from "@/components/studio/app-switcher";
import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { logout, useAuthStore } from "@/lib/auth/session";
import { useI18n } from "@/lib/i18n/context";
import { useTenant } from "@/lib/tenant/context";
import Link from "next/link";

import { Breadcrumbs } from "./breadcrumbs";

function initials(name: string, email: string): string {
  const base = name.trim() || email;
  return base.slice(0, 2).toUpperCase();
}

export function Topbar({ onOpenSidebar }: { onOpenSidebar: () => void }) {
  const user = useAuthStore((s) => s.user);
  const { t } = useI18n();
  const { branding } = useTenant();

  return (
    <header className="flex h-14 items-center gap-2 border-b border-border bg-background px-3">
      <Button
        variant="ghost"
        size="icon"
        className="lg:hidden"
        aria-label="Open navigation"
        onClick={onOpenSidebar}
      >
        <Menu className="size-5" />
      </Button>

      <BrandMark
        logoUrl={branding?.logo_url}
        appName={branding?.app_name}
        className="hidden text-sm sm:flex"
        size={22}
      />

      <AppSwitcher />

      <Breadcrumbs />

      <div className="ml-auto flex items-center gap-1">
        {/* Opens the Cmd/Ctrl+K command palette (mounted in the app shell). */}
        <Button
          variant="outline"
          size="sm"
          className="hidden gap-2 text-muted-foreground sm:flex"
          aria-label="Search"
          onClick={() =>
            document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }))
          }
        >
          <Search className="size-4" />
          <span>{t("action.search", "Search")}</span>
          <kbd className="ml-2 rounded border border-border px-1 text-xs">⌘K</kbd>
        </Button>

        <OfflineIndicator />

        <NotificationCenter />

        <LanguageSwitcher />

        <ThemeToggle />

        <DropdownMenu>
          <DropdownMenuTrigger aria-label="User menu" className="rounded-full focus:outline-none focus:ring-2 focus:ring-ring">
            <Avatar className="size-8">
              <AvatarFallback>{initials(user?.full_name ?? "", user?.email ?? "U")}</AvatarFallback>
            </Avatar>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-56" align="end">
            <DropdownMenuLabel className="truncate font-normal">
              {user?.email ?? "Signed in"}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/settings/security">{t("nav.security", "Security")}</Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/settings/notifications">{t("nav.notification_settings", "Notification settings")}</Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/settings/sessions">{t("nav.sessions", "Sessions")}</Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => logout()}>{t("action.sign_out", "Sign out")}</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
