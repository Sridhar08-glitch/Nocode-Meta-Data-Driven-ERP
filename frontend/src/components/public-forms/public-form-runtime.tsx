"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { ErrorState } from "@/components/ui/states";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/errors";
import type { FormField, FormSchema } from "@/lib/metadata/types";
import { usePublicFormSchema, useSubmitPublicForm } from "@/lib/public-forms/hooks";

function optionsOf(field: FormField): { value: string; label: string }[] {
  const raw = (field.config?.choices ?? field.config?.options ?? []) as unknown[];
  return raw.map((o) =>
    typeof o === "string" ? { value: o, label: o } : (o as { value: string; label: string }),
  );
}

/** Public form runtime (Phase F3.8): renders a public form schema + honeypot, submits anonymously. */
export function PublicFormRuntime({ formId }: { formId: string }) {
  const schema = usePublicFormSchema(formId);
  const submit = useSubmitPublicForm(formId);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [honeypot, setHoneypot] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const fieldsBySlug = useMemo(() => {
    const map = new Map<string, FormField>();
    (schema.data?.schema.fields ?? []).forEach((f) => map.set(f.slug, f));
    return map;
  }, [schema.data]);

  if (schema.isLoading) return <Skeleton className="h-64 w-full" />;
  if (schema.isError || !schema.data) return <ErrorState title="Form unavailable" description="This form may be closed or does not exist." />;

  const def: PublicFormDef = schema.data;
  const honeypotField = def.honeypot_field;

  const set = (slug: string, v: unknown) => setValues((cur) => ({ ...cur, [slug]: v }));

  function missingRequired(): boolean {
    for (const f of def.schema.fields) {
      if (f.is_required && !f.is_hidden && !f.is_readonly) {
        const v = values[f.slug];
        if (v === undefined || v === "" || v === null) return true;
      }
    }
    return false;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (missingRequired()) {
      setError("Please fill in all required fields.");
      return;
    }
    try {
      await submit.mutateAsync({ ...values, [honeypotField]: honeypot });
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong — please try again.");
    }
  }

  if (done) {
    return (
      <div className="rounded-lg border p-6 text-center">
        <h2 className="text-lg font-semibold">Thank you</h2>
        <p className="text-sm text-muted-foreground">Your submission has been received.</p>
      </div>
    );
  }

  return (
    <form className="space-y-5" onSubmit={onSubmit} aria-label={def.name}>
      <h1 className="text-2xl font-semibold">{def.name}</h1>
      {def.schema.sections.map((section) => (
        <fieldset key={section.key} className="space-y-4">
          {section.title && <legend className="text-sm font-medium text-muted-foreground">{section.title}</legend>}
          {section.fields.map((slug) => {
            const f = fieldsBySlug.get(slug);
            if (!f || f.is_hidden) return null;
            return <FieldInput key={slug} field={f} value={values[slug]} onChange={(v) => set(slug, v)} />;
          })}
        </fieldset>
      ))}

      {/* honeypot — visually hidden, bots fill it */}
      <input
        type="text"
        name={honeypotField}
        value={honeypot}
        onChange={(e) => setHoneypot(e.target.value)}
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
        className="absolute left-[-9999px] h-0 w-0 opacity-0"
      />

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <Button type="submit" disabled={submit.isPending}>
        {submit.isPending ? "Submitting…" : String(def.settings?.submit_text ?? "Submit")}
      </Button>
    </form>
  );
}

interface PublicFormDef {
  name: string;
  honeypot_field: string;
  settings: Record<string, unknown>;
  schema: FormSchema;
}

function FieldInput({ field, value, onChange }: { field: FormField; value: unknown; onChange: (v: unknown) => void }) {
  const id = `f-${field.slug}`;
  const label = (
    <Label htmlFor={id}>
      {field.name}
      {field.is_required && <span className="ml-0.5 text-destructive">*</span>}
    </Label>
  );
  const t = field.field_type;

  if (t === "boolean" || t === "checkbox") {
    return (
      <label className="flex items-center gap-2 text-sm">
        <Checkbox id={id} checked={!!value} onCheckedChange={(v) => onChange(!!v)} aria-label={field.name} />
        {field.name}
      </label>
    );
  }
  if (t === "select" || t === "lookup") {
    return (
      <div className="space-y-1.5">
        {label}
        <Select value={(value as string) || undefined} onValueChange={onChange}>
          <SelectTrigger id={id} aria-label={field.name} className="w-full">
            <SelectValue placeholder="Select…" />
          </SelectTrigger>
          <SelectContent>
            {optionsOf(field).map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    );
  }
  if (t === "long_text" || t === "textarea" || t === "rich_text") {
    return (
      <div className="space-y-1.5">
        {label}
        <Textarea id={id} rows={4} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />
      </div>
    );
  }
  const inputType = t === "integer" || t === "decimal" || t === "number" || t === "currency" ? "number" : t === "date" ? "date" : t === "email" ? "email" : "text";
  return (
    <div className="space-y-1.5">
      {label}
      <Input id={id} type={inputType} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}
