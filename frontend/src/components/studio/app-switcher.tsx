"use client";

import { Check, LayoutGrid } from "lucide-react";
import { useRouter } from "next/navigation";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useActiveApp } from "@/lib/studio/active-app";
import { useAppSwitcher } from "@/lib/studio/hooks";
import { cn } from "@/lib/utils";

/**
 * Topbar application switcher (Phase F2.8). Lists published apps the member may see (the
 * `/applications/switcher/` endpoint, role-gated server-side). Selecting an app sets it active —
 * the sidebar resolves its navigation and `/home` resolves its home layout. Hidden when no apps
 * are published, so workspaces without Studio apps see no change.
 */
export function AppSwitcher() {
  const router = useRouter();
  const { activeAppId, setActiveApp } = useActiveApp();
  const switcher = useAppSwitcher();
  const apps = switcher.data?.results ?? [];

  if (apps.length === 0) return null;

  const active = apps.find((a) => a.id === activeAppId) ?? null;

  function choose(id: string | null) {
    setActiveApp(id);
    router.push("/home");
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Switch application"
        className="flex items-center gap-2 rounded-md border border-input px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      >
        <LayoutGrid className="size-4" />
        <span className="max-w-32 truncate">{active?.name ?? "All apps"}</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        <DropdownMenuLabel className="font-normal text-muted-foreground">Applications</DropdownMenuLabel>
        <DropdownMenuItem onSelect={() => choose(null)}>
          <span className="flex-1">All apps</span>
          <Check className={cn("size-4", activeAppId ? "opacity-0" : "opacity-100")} />
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {apps.map((a) => (
          <DropdownMenuItem key={a.id} onSelect={() => choose(a.id)}>
            <span className="flex-1 truncate">{a.name}</span>
            <Check className={cn("size-4", a.id === activeAppId ? "opacity-100" : "opacity-0")} />
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
