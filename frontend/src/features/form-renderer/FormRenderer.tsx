"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState } from "react";
import { Controller, useForm, type Resolver } from "react-hook-form";
import { z } from "zod";

import { componentForKind } from "@/components/fields/registry";
import { ReadOnlyField } from "@/components/fields/inputs";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Stepper } from "@/components/ui/stepper";
import { getFieldType, isReadOnlyField } from "@/lib/metadata/field-types";
import { makeDefaultValues, writableFields } from "@/lib/metadata/form-schema";
import type { FormField, FormSchema, FormSection } from "@/lib/metadata/types";

import { evaluateHiddenFields, type ConditionalRule } from "./conditional";

export interface FormRendererProps {
  schema: FormSchema;
  /** Existing record values (edit mode) merged over type defaults. */
  initialValues?: Record<string, unknown>;
  onSubmit: (values: Record<string, unknown>) => void | Promise<void>;
  submitLabel?: string;
  disabled?: boolean;
}

/**
 * THE single Form Renderer (F1.6). Consumes a resolved FormSchema + the field-type
 * registry. Validation is a dynamic Zod over the *visible writable* fields (so
 * conditionally-hidden required fields never block submit). Layout is sections, or a
 * multi-step wizard when `layout_type === "wizard"` (per-step validation).
 */
export function FormRenderer({
  schema,
  initialValues,
  onSubmit,
  submitLabel = "Save",
  disabled,
}: FormRendererProps) {
  const fieldBySlug = useMemo(
    () => new Map(schema.fields.map((f) => [f.slug, f])),
    [schema.fields],
  );

  const defaults = useMemo(
    () => ({ ...makeDefaultValues(schema), ...(initialValues ?? {}) }),
    [schema, initialValues],
  );

  // Dynamic resolver: validate only visible, writable fields.
  const resolver: Resolver<Record<string, unknown>> = useMemo(
    () => async (values, ctx, opts) => {
      const hidden = evaluateHiddenFields(
        schema.conditional_rules as ConditionalRule[],
        values,
      );
      const shape: Record<string, z.ZodTypeAny> = {};
      for (const f of writableFields(schema)) {
        if (!hidden.has(f.slug)) shape[f.slug] = getFieldType(f.field_type).buildZod(f);
      }
      return zodResolver(z.object(shape))(values, ctx, opts);
    },
    [schema],
  );

  const form = useForm<Record<string, unknown>>({ resolver, defaultValues: defaults, mode: "onBlur" });
  const values = form.watch();
  const hidden = useMemo(
    () => evaluateHiddenFields(schema.conditional_rules as ConditionalRule[], values),
    [schema.conditional_rules, values],
  );

  const sections = schema.sections.length
    ? schema.sections
    : [{ key: "main", title: "", columns: 1, fields: schema.fields.map((f) => f.slug), condition: null }];
  const isWizard = schema.layout_type === "wizard" && sections.length > 1;
  const [step, setStep] = useState(0);

  async function next() {
    const slugs = sections[step].fields.filter((s) => !hidden.has(s));
    const ok = await form.trigger(slugs);
    if (ok) setStep((s) => Math.min(s + 1, sections.length - 1));
  }

  const submit = form.handleSubmit((vals) => {
    // Drop conditionally-hidden values from the payload.
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(vals)) if (!hidden.has(k)) out[k] = v;
    return onSubmit(out);
  });

  const renderField = (slug: string) => {
    const field = fieldBySlug.get(slug);
    if (!field || field.is_hidden || hidden.has(slug)) return null;
    return (
      <FieldRow
        key={slug}
        field={field}
        control={form.control}
        initialValue={defaults[slug]}
        disabled={disabled}
      />
    );
  };

  const visibleSections = isWizard ? [sections[step]] : sections;

  return (
    <form onSubmit={submit} noValidate className="space-y-6">
      {isWizard && (
        <Stepper
          current={step}
          steps={sections.map((s, i) => ({ id: s.key, label: s.title || `Step ${i + 1}` }))}
        />
      )}

      {visibleSections.map((section: FormSection) => (
        <fieldset key={section.key} className="space-y-4">
          {section.title && <legend className="text-sm font-semibold">{section.title}</legend>}
          <div
            className="grid gap-4"
            style={{ gridTemplateColumns: `repeat(${Math.max(1, section.columns)}, minmax(0, 1fr))` }}
          >
            {section.fields.map(renderField)}
          </div>
        </fieldset>
      ))}

      <div className="flex justify-end gap-2">
        {isWizard && step > 0 && (
          <Button type="button" variant="outline" onClick={() => setStep((s) => s - 1)}>
            Back
          </Button>
        )}
        {isWizard && step < sections.length - 1 ? (
          <Button type="button" onClick={next}>
            Next
          </Button>
        ) : (
          <Button type="submit" disabled={disabled || form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Saving…" : submitLabel}
          </Button>
        )}
      </div>
    </form>
  );
}

function FieldRow({
  field,
  control,
  initialValue,
  disabled,
}: {
  field: FormField;
  control: ReturnType<typeof useForm<Record<string, unknown>>>["control"];
  initialValue: unknown;
  disabled?: boolean;
}) {
  const kind = getFieldType(field.field_type).kind;
  const id = `field-${field.slug}`;
  const readOnly = isReadOnlyField(field);
  const Component = componentForKind(kind);

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1">
        <Label htmlFor={id}>{field.name}</Label>
        {field.is_required && !readOnly && (
          <span aria-hidden className="text-destructive">
            *
          </span>
        )}
      </div>

      {readOnly ? (
        <ReadOnlyField field={field} id={id} value={initialValue} onChange={() => {}} onBlur={() => {}} />
      ) : (
        <Controller
          name={field.slug}
          control={control}
          render={({ field: rhf, fieldState }) => (
            <>
              <Component
                field={field}
                id={id}
                value={rhf.value}
                onChange={rhf.onChange}
                onBlur={rhf.onBlur}
                disabled={disabled}
                invalid={!!fieldState.error}
              />
              {fieldState.error?.message && (
                <p className="text-xs text-destructive" role="alert">
                  {fieldState.error.message}
                </p>
              )}
            </>
          )}
        />
      )}

      {field.description && (
        <p id={`${id}-desc`} className="text-xs text-muted-foreground">
          {field.description}
        </p>
      )}
    </div>
  );
}
