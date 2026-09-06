"use client";

import Link from "next/link";
import { useState } from "react";

import { CreateWorkspace } from "@/components/tenant/create-workspace";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { I18nProvider } from "@/lib/i18n/context";
import { ActiveAppProvider } from "@/lib/studio/active-app";
import { useTenant } from "@/lib/tenant/context";

import { CommandPalette } from "./command-palette";
import { SidebarNav } from "./sidebar-nav";
import { Topbar } from "./topbar";
import { WorkspaceSwitcher } from "./workspace-switcher";

function SidebarInner({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border p-3">
        <WorkspaceSwitcher />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <SidebarNav onNavigate={onNavigate} />
      </div>
      <div className="border-t border-border p-3">
        <Link href="/dev/components" className="text-xs text-muted-foreground hover:text-foreground">
          Design system
        </Link>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { isLoading, workspaces } = useTenant();
  const [mobileOpen, setMobileOpen] = useState(false);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (workspaces.length === 0) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6">
        <CreateWorkspace />
        <p className="text-xs text-muted-foreground">
          Already part of a team? Ask an admin to add you, then refresh.
        </p>
      </div>
    );
  }

  return (
    <I18nProvider>
      <ActiveAppProvider>
      <div className="flex h-screen">
        <CommandPalette />
        <aside className="hidden w-64 shrink-0 border-r border-border lg:block">
          <SidebarInner />
        </aside>

        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetContent side="left" className="w-72 p-0">
            <SheetTitle className="sr-only">Navigation</SheetTitle>
            <SidebarInner onNavigate={() => setMobileOpen(false)} />
          </SheetContent>
        </Sheet>

        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar onOpenSidebar={() => setMobileOpen(true)} />
          <main className="min-h-0 flex-1 overflow-y-auto p-6">{children}</main>
        </div>
      </div>
      </ActiveAppProvider>
    </I18nProvider>
  );
}
