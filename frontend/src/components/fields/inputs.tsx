"use client";

import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { getFieldType } from "@/lib/metadata/field-types";

import type { FieldProps } from "./field-props";

const TEXT_INPUT_TYPE: Record<string, string> = {
  email: "email",
  phone: "tel",
  url: "url",
  text: "text",
  location: "text",
  barcode: "text",
};

export function TextInputField({ field, id, value, onChange, onBlur, disabled, invalid }: FieldProps) {
  return (
    <Input
      id={id}
      type={TEXT_INPUT_TYPE[field.field_type] ?? "text"}
      value={(value as string) ?? ""}
      onChange={(e) => onChange(e.target.value)}
      onBlur={onBlur}
      disabled={disabled}
      aria-invalid={invalid || undefined}
      aria-describedby={field.description ? `${id}-desc` : undefined}
    />
  );
}

export function TextareaField({ field, id, value, onChange, onBlur, disabled, invalid }: FieldProps) {
  return (
    <Textarea
      id={id}
      value={(value as string) ?? ""}
      onChange={(e) => onChange(e.target.value)}
      onBlur={onBlur}
      disabled={disabled}
      aria-invalid={invalid || undefined}
      aria-describedby={field.description ? `${id}-desc` : undefined}
    />
  );
}

export function NumberInputField({ id, value, onChange, onBlur, disabled, invalid }: FieldProps) {
  return (
    <Input
      id={id}
      type="number"
      inputMode="decimal"
      value={value === null || value === undefined ? "" : (value as number | string)}
      onChange={(e) => onChange(e.target.value)}
      onBlur={onBlur}
      disabled={disabled}
      aria-invalid={invalid || undefined}
    />
  );
}

const DATE_INPUT_TYPE: Record<string, string> = {
  date: "date",
  datetime: "datetime-local",
  time: "time",
};

export function DateField({ field, id, value, onChange, onBlur, disabled, invalid }: FieldProps) {
  return (
    <Input
      id={id}
      type={DATE_INPUT_TYPE[field.field_type] ?? "date"}
      value={(value as string) ?? ""}
      onChange={(e) => onChange(e.target.value)}
      onBlur={onBlur}
      disabled={disabled}
      aria-invalid={invalid || undefined}
    />
  );
}

export function JsonField({ id, value, onChange, onBlur, disabled, invalid }: FieldProps) {
  const text = typeof value === "string" ? value : value == null ? "" : JSON.stringify(value, null, 2);
  return (
    <Textarea
      id={id}
      className="font-mono text-xs"
      value={text}
      onChange={(e) => onChange(e.target.value)}
      onBlur={onBlur}
      disabled={disabled}
      aria-invalid={invalid || undefined}
    />
  );
}

export function FileField({ id, onChange, onBlur, disabled }: FieldProps) {
  // F1.6 captures the file selection; upload through the documents API lands in F1.7.
  return (
    <Input
      id={id}
      type="file"
      onChange={(e) => onChange(e.target.files?.[0]?.name ?? "")}
      onBlur={onBlur}
      disabled={disabled}
    />
  );
}

export function ReadOnlyField({ field, id, value }: FieldProps) {
  const display = getFieldType(field.field_type).format(value, field);
  return (
    <output
      id={id}
      className="block min-h-10 rounded-md border border-dashed border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
    >
      {display || "—"}
    </output>
  );
}
