"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/manufacturing", label: "Overview", exact: true },
  { href: "/manufacturing/boms", label: "BOMs & work centers" },
  { href: "/manufacturing/orders", label: "Production orders" },
  { href: "/manufacturing/mrp", label: "MRP" },
  { href: "/manufacturing/quality", label: "Quality & traceability" },
];

/** Sub-navigation across the manufacturing engine pages. */
export function ManufacturingNav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-wrap gap-1 border-b pb-2" aria-label="Manufacturing">
      {LINKS.map((l) => {
        const active = l.exact ? pathname === l.href : pathname.startsWith(l.href);
        return (
          <Link
            key={l.href}
            href={l.href}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm transition-colors",
              active
                ? "bg-primary/10 font-medium text-primary"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
