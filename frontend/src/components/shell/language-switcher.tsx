"use client";

import { Languages } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useI18n } from "@/lib/i18n/context";
import { cn } from "@/lib/utils";

function localeName(locale: string): string {
  try {
    return new Intl.DisplayNames([locale], { type: "language" }).of(locale.slice(0, 2)) ?? locale;
  } catch {
    return locale;
  }
}

/** Language switcher (Phase F2.6) — picks among the workspace's enabled locales; persists per-user. */
export function LanguageSwitcher() {
  const { locale, setLocale, availableLocales } = useI18n();
  if (availableLocales.length <= 1) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Change language"
        className="inline-flex size-9 items-center justify-center rounded-md hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring"
      >
        <Languages className="size-4" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Language</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {availableLocales.map((l) => (
          <DropdownMenuItem key={l} onSelect={() => setLocale(l)}>
            <span className={cn(l === locale && "font-medium text-primary")}>
              {localeName(l)} <span className="text-xs text-muted-foreground">{l}</span>
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
