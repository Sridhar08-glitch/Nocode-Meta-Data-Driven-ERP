"use client";

import { Check, ChevronsUpDown, X } from "lucide-react";
import { createContext, useContext, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import { apiGet } from "@/lib/api/request";
import type { FormField } from "@/lib/metadata/types";
import { cn } from "@/lib/utils";

import type { FieldProps } from "./field-props";

export interface RelationOption {
  value: string;
  label: string;
}
export type RelationLoader = (field: FormField, query: string) => Promise<RelationOption[]>;

/** Default loader: search the target entity's title field via the auto-CRUD API + NQL. */
export const defaultRelationLoader: RelationLoader = async (field, query) => {
  const cfg = field.config ?? {};
  const target = cfg.target_entity_slug as string | undefined;
  if (!target) return [];
  const display = (cfg.display_field as string) ?? "name";
  let path = `/api/v1/data/${target}/?limit=20`;
  if (query) {
    const filter = JSON.stringify({ field: display, op: "contains", value: query });
    path += `&filter=${encodeURIComponent(filter)}`;
  }
  const data = await apiGet<{ results: Record<string, unknown>[] }>(path);
  return (data.results ?? []).map((r) => ({
    value: String(r.id),
    label: String(r[display] ?? r.id),
  }));
};

const RelationLoaderContext = createContext<RelationLoader>(defaultRelationLoader);

export function RelationLoaderProvider({
  loader,
  children,
}: {
  loader: RelationLoader;
  children: React.ReactNode;
}) {
  return <RelationLoaderContext.Provider value={loader}>{children}</RelationLoaderContext.Provider>;
}

export function useRelationLoader(): RelationLoader {
  return useContext(RelationLoaderContext);
}

const MULTI_KINDS = new Set(["multi_lookup", "multi_user"]);

export function RelationField({ field, id, value, onChange, disabled }: FieldProps) {
  const loader = useRelationLoader();
  const multi = MULTI_KINDS.has(field.field_type);
  const selected: string[] = multi
    ? Array.isArray(value)
      ? (value as string[])
      : []
    : value
      ? [String(value)]
      : [];

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<RelationOption[]>([]);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    const t = setTimeout(() => {
      loader(field, query)
        .then((opts) => {
          if (cancelled) return;
          setOptions(opts);
          setLabels((prev) => {
            const next = { ...prev };
            for (const o of opts) next[o.value] = o.label;
            return next;
          });
        })
        .finally(() => !cancelled && setLoading(false));
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [open, query, field, loader]);

  function pick(optionValue: string) {
    if (multi) {
      const next = selected.includes(optionValue)
        ? selected.filter((v) => v !== optionValue)
        : [...selected, optionValue];
      onChange(next);
    } else {
      onChange(optionValue);
      setOpen(false);
    }
  }

  function remove(optionValue: string) {
    if (multi) onChange(selected.filter((v) => v !== optionValue));
    else onChange("");
  }

  return (
    <div>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            id={id}
            type="button"
            variant="outline"
            disabled={disabled}
            className="w-full justify-between font-normal"
          >
            <span className="truncate text-muted-foreground">
              {selected.length ? `${selected.length} selected` : "Search…"}
            </span>
            <ChevronsUpDown className="size-4 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-72 p-0">
          <div className="border-b border-border p-2">
            <Input
              autoFocus
              placeholder="Search…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <div className="max-h-60 overflow-y-auto p-1">
            {loading && (
              <div className="flex justify-center p-3">
                <Spinner />
              </div>
            )}
            {!loading && options.length === 0 && (
              <p className="p-3 text-center text-sm text-muted-foreground">No matches</p>
            )}
            {!loading &&
              options.map((o) => (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => pick(o.value)}
                  className="flex w-full items-center justify-between rounded-sm px-2 py-1.5 text-left text-sm hover:bg-muted"
                >
                  <span className="truncate">{o.label}</span>
                  <Check
                    className={cn("size-4", selected.includes(o.value) ? "opacity-100" : "opacity-0")}
                  />
                </button>
              ))}
          </div>
        </PopoverContent>
      </Popover>

      {selected.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {selected.map((v) => (
            <Badge key={v} variant="secondary" className="gap-1">
              {labels[v] ?? v}
              <button type="button" aria-label="Remove" onClick={() => remove(v)}>
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
