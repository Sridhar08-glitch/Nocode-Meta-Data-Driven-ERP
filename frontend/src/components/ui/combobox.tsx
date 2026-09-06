"use client";

import { Check, ChevronsUpDown } from "lucide-react";
import { useId, useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface ComboboxOption {
  value: string;
  label?: string;
}

/**
 * Searchable single-select built on the existing Popover primitive (Phase F2.7). Used for the
 * IANA timezone picker. Accessible: trigger is a `combobox`, the list is a `listbox` of `option`s.
 */
export function Combobox({
  value,
  onChange,
  options,
  id,
  placeholder = "Select…",
  searchPlaceholder = "Search…",
  "aria-label": ariaLabel,
  triggerClassName,
  maxVisible = 100,
}: {
  value: string;
  onChange: (value: string) => void;
  options: ComboboxOption[];
  id?: string;
  placeholder?: string;
  searchPlaceholder?: string;
  "aria-label"?: string;
  triggerClassName?: string;
  maxVisible?: number;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const listboxId = useId();

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const list = needle
      ? options.filter((o) => (o.label ?? o.value).toLowerCase().includes(needle) || o.value.toLowerCase().includes(needle))
      : options;
    return list.slice(0, maxVisible);
  }, [options, query, maxVisible]);

  function select(v: string) {
    onChange(v);
    setOpen(false);
    setQuery("");
  }

  const selectedLabel = options.find((o) => o.value === value)?.label ?? value;

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setQuery("");
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          id={id}
          role="combobox"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-haspopup="listbox"
          aria-label={ariaLabel}
          className={cn(
            "flex h-9 items-center justify-between gap-2 rounded-md border border-input bg-background px-3 text-sm",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            triggerClassName,
          )}
        >
          <span className={cn("truncate", !value && "text-muted-foreground")}>{value ? selectedLabel : placeholder}</span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 p-0">
        <Input
          aria-label={`${ariaLabel ?? "options"} search`}
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={searchPlaceholder}
          className="border-0 border-b border-border focus-visible:ring-0"
        />
        <ul id={listboxId} role="listbox" aria-label={ariaLabel} className="max-h-64 overflow-y-auto p-1">
          {filtered.length === 0 ? (
            <li className="px-2 py-6 text-center text-sm text-muted-foreground">No matches.</li>
          ) : (
            filtered.map((o) => {
              const selected = o.value === value;
              return (
                <li key={o.value}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={selected}
                    onClick={() => select(o.value)}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted",
                      selected && "bg-muted",
                    )}
                  >
                    <Check className={cn("size-4 shrink-0", selected ? "opacity-100" : "opacity-0")} />
                    <span className="truncate">{o.label ?? o.value}</span>
                  </button>
                </li>
              );
            })
          )}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
