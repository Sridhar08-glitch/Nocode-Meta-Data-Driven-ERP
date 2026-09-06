"use client";

import { Check, ChevronsUpDown, Plus } from "lucide-react";
import { useRouter } from "next/navigation";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTenant } from "@/lib/tenant/context";
import { cn } from "@/lib/utils";

export function WorkspaceSwitcher() {
  const { workspace, workspaces, switchWorkspace } = useTenant();
  const router = useRouter();
  if (!workspace) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex w-full items-center justify-between gap-2 rounded-md border border-border px-3 py-2 text-left text-sm hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring">
        <span className="min-w-0">
          <span className="block truncate font-medium">{workspace.name}</span>
          <span className="block truncate text-xs capitalize text-muted-foreground">
            {workspace.plan} · {workspace.role}
          </span>
        </span>
        <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56">
        <DropdownMenuLabel>Workspaces</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {workspaces.map((w) => (
          <DropdownMenuItem key={w.id} onSelect={() => switchWorkspace(w.slug)}>
            <span className="flex-1 truncate">{w.name}</span>
            <Check className={cn("size-4", w.slug === workspace.slug ? "opacity-100" : "opacity-0")} />
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => router.push("/workspaces/new")}>
          <Plus className="size-4" />
          <span className="flex-1">New workspace</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
