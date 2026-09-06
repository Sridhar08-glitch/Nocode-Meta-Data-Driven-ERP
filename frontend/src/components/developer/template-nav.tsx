"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/templates", label: "Notifications" },
  { href: "/templates/email", label: "Email" },
  { href: "/templates/documents", label: "Documents (PDF)" },
];

/** Shared sub-nav across the three template surfaces (notifications / email / documents). */
export function TemplateNav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-wrap gap-2" aria-label="Template types">
      {LINKS.map((l) => {
        const active = l.href === "/templates" ? pathname === "/templates" : pathname.startsWith(l.href);
        return (
          <Link
            key={l.href}
            href={l.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "rounded-md border px-3 py-1.5 text-sm transition-colors",
              active ? "bg-primary/10 font-medium text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
