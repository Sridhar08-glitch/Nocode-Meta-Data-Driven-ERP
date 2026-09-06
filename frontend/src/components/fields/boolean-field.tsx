"use client";

import { Switch } from "@/components/ui/switch";

import type { FieldProps } from "./field-props";

export function BooleanField({ id, value, onChange, disabled }: FieldProps) {
  return (
    <Switch
      id={id}
      checked={!!value}
      onCheckedChange={(checked) => onChange(checked)}
      disabled={disabled}
    />
  );
}
