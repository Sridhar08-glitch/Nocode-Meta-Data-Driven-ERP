"use client";

import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { optionList, type FieldProps } from "./field-props";

export function SelectField({ field, id, value, onChange, disabled }: FieldProps) {
  const options = optionList(field);
  return (
    <Select value={(value as string) ?? ""} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger id={id} aria-label={field.name}>
        <SelectValue placeholder="Select…" />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function MultiSelectField({ field, id, value, onChange, disabled }: FieldProps) {
  const options = optionList(field);
  const selected = Array.isArray(value) ? (value as string[]) : [];

  function toggle(optionValue: string, checked: boolean) {
    onChange(checked ? [...selected, optionValue] : selected.filter((v) => v !== optionValue));
  }

  return (
    <div id={id} role="group" aria-label={field.name} className="space-y-2">
      {options.map((o) => (
        <label key={o.value} className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={selected.includes(o.value)}
            onCheckedChange={(c) => toggle(o.value, c === true)}
            disabled={disabled}
          />
          {o.label}
        </label>
      ))}
    </div>
  );
}
