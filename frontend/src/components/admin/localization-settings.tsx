"use client";

import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { useEntities } from "@/lib/metadata/hooks";
import {
  useCreateEntityLabel,
  useDeleteEntityLabel,
  useEntityLabels,
  useLocale,
  useSetLocale,
} from "@/lib/localization/hooks";

/** Backend WorkspaceLocale defaults (apps/localization/models.py). */
const DEFAULT_LOCALE = { default_locale: "en-US", default_timezone: "UTC", default_currency: "USD", enabled_locales: "" };

/** Localization settings (Phase F3.1 + polish): locale defaults (with restore) + searchable labels. */
export function LocalizationSettings() {
  return (
    <div className="space-y-8">
      <LocaleDefaults />
      <EntityLabels />
    </div>
  );
}

function LocaleDefaults() {
  const locale = useLocale();
  const setLocale = useSetLocale();
  const [defaultLocale, setDefaultLocale] = useState("");
  const [timezone, setTimezone] = useState("");
  const [currency, setCurrency] = useState("");
  const [enabled, setEnabled] = useState("");
  const [confirmReset, setConfirmReset] = useState(false);

  useEffect(() => {
    const d = locale.data;
    if (d) {
      setDefaultLocale(d.default_locale);
      setTimezone(d.default_timezone);
      setCurrency(d.default_currency);
      setEnabled((d.enabled_locales ?? []).join(", "));
    }
  }, [locale.data]);

  if (locale.isLoading) return <Skeleton className="h-40 w-full" />;
  if (locale.isError) return <ErrorState title="Couldn't load locale" />;

  async function save() {
    try {
      await setLocale.mutateAsync({
        default_locale: defaultLocale.trim(),
        default_timezone: timezone.trim(),
        default_currency: currency.trim().toUpperCase(),
        enabled_locales: enabled.split(",").map((s) => s.trim()).filter(Boolean),
      });
      toast.success("Locale saved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save locale");
    }
  }

  function restore() {
    setDefaultLocale(DEFAULT_LOCALE.default_locale);
    setTimezone(DEFAULT_LOCALE.default_timezone);
    setCurrency(DEFAULT_LOCALE.default_currency);
    setEnabled(DEFAULT_LOCALE.enabled_locales);
    setConfirmReset(false);
    toast.info("Defaults restored — click Save to apply");
  }

  return (
    <section className="space-y-4">
      <h2 className="text-sm font-medium text-muted-foreground">Defaults</h2>
      <div className="flex flex-wrap gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="l-locale">Default locale</Label>
          <Input id="l-locale" value={defaultLocale} onChange={(e) => setDefaultLocale(e.target.value)} placeholder="en-US" className="w-32" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="l-tz">Timezone</Label>
          <Input id="l-tz" value={timezone} onChange={(e) => setTimezone(e.target.value)} placeholder="UTC" className="w-44" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="l-cur">Currency</Label>
          <Input id="l-cur" value={currency} onChange={(e) => setCurrency(e.target.value)} placeholder="USD" className="w-24" />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="l-enabled">Enabled locales (comma-separated)</Label>
        <Input id="l-enabled" value={enabled} onChange={(e) => setEnabled(e.target.value)} placeholder="en-US, fr-FR, ar-SA" className="w-96 max-w-full" />
      </div>
      <div className="flex gap-2">
        <Button onClick={save} disabled={setLocale.isPending}>
          {setLocale.isPending ? "Saving…" : "Save defaults"}
        </Button>
        <Button variant="outline" onClick={() => setConfirmReset(true)}>
          Restore defaults
        </Button>
      </div>

      <Dialog open={confirmReset} onOpenChange={setConfirmReset}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Restore locale defaults?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This resets locale, timezone, and currency to en-US / UTC / USD in the form. Nothing is
            saved until you click <strong>Save defaults</strong>.
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmReset(false)}>
              Cancel
            </Button>
            <Button onClick={restore}>Restore defaults</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

function EntityLabels() {
  const entities = useEntities();
  const labels = useEntityLabels();
  const create = useCreateEntityLabel();
  const del = useDeleteEntityLabel();
  const [entityId, setEntityId] = useState("");
  const [locale, setLocaleCode] = useState("");
  const [singular, setSingular] = useState("");
  const [plural, setPlural] = useState("");
  const [search, setSearch] = useState("");

  const valid = !!entityId && !!locale.trim() && !!singular.trim() && !!plural.trim();
  const rows = labels.data?.results ?? [];
  const entityName = (id: string | null) => entities.data?.find((e) => e.id === id)?.name ?? id ?? "—";

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((l) =>
      [entityName(l.entity_id), l.locale, l.singular, l.plural].some((v) => (v ?? "").toLowerCase().includes(q)),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, search, entities.data]);

  async function add() {
    if (!valid) return;
    try {
      await create.mutateAsync({ entity_id: entityId, locale: locale.trim(), singular: singular.trim(), plural: plural.trim() });
      toast.success("Label added");
      setSingular("");
      setPlural("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not add label");
    }
  }
  async function remove(id: string) {
    try {
      await del.mutateAsync(id);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove label");
    }
  }
  function exportJson() {
    const payload = rows.map((l) => ({ entity_id: l.entity_id, locale: l.locale, singular: l.singular, plural: l.plural }));
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "entity-labels.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="space-y-4 border-t pt-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-medium text-muted-foreground">Entity labels</h2>
        <Button variant="outline" size="sm" onClick={exportJson} disabled={rows.length === 0}>
          Export JSON
        </Button>
      </div>

      <Input
        aria-label="Search translations"
        placeholder="Search translations…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
      />

      {rows.length === 0 ? (
        <EmptyState title="No entity labels" description="Translate entity names per locale below." className="border-0 p-0 text-left" />
      ) : filtered.length === 0 ? (
        <p className="text-sm text-muted-foreground">No labels match “{search}”.</p>
      ) : (
        <ul className="space-y-1.5">
          {filtered.map((l) => (
            <li key={l.id} className="flex items-center justify-between gap-2 rounded-md border p-2 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{entityName(l.entity_id)}</span>
                <Badge variant="outline">{l.locale}</Badge>
                <span className="text-muted-foreground">{l.singular} / {l.plural}</span>
              </span>
              <Button variant="ghost" size="sm" aria-label={`Remove label ${l.id}`} onClick={() => remove(l.id)} disabled={del.isPending}>
                ✕
              </Button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-end gap-2 border-t pt-3">
        <div className="space-y-1.5">
          <Label htmlFor="el-entity">Entity</Label>
          <Select value={entityId || undefined} onValueChange={setEntityId}>
            <SelectTrigger id="el-entity" className="w-40">
              <SelectValue placeholder="Pick entity" />
            </SelectTrigger>
            <SelectContent>
              {(entities.data ?? []).map((e) => (
                <SelectItem key={e.id} value={e.id}>
                  {e.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="el-locale">Locale</Label>
          <Input id="el-locale" value={locale} onChange={(e) => setLocaleCode(e.target.value)} placeholder="fr-FR" className="h-9 w-24" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="el-singular">Singular</Label>
          <Input id="el-singular" value={singular} onChange={(e) => setSingular(e.target.value)} className="h-9 w-32" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="el-plural">Plural</Label>
          <Input id="el-plural" value={plural} onChange={(e) => setPlural(e.target.value)} className="h-9 w-32" />
        </div>
        <Button onClick={add} disabled={!valid || create.isPending}>
          Add label
        </Button>
      </div>
    </section>
  );
}
