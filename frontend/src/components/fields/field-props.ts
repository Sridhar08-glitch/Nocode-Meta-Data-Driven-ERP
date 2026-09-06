import type { FormField } from "@/lib/metadata/types";

/** Common props every field component receives (RHF-wired by the FormRenderer). */
export interface FieldProps {
  field: FormField;
  id: string;
  value: unknown;
  onChange: (value: unknown) => void;
  onBlur: () => void;
  disabled?: boolean;
  invalid?: boolean;
}

export function optionList(field: FormField): { value: string; label: string }[] {
  // Backend field configs carry the choice list under `choices` (a list of strings or
  // {value,label} objects); some carry `options`. Accept both so select/status/multiselect
  // fields render their options instead of an empty dropdown.
  const cfg = field.config as Record<string, unknown> | undefined;
  const raw = ((cfg?.options ?? cfg?.choices ?? []) as unknown[]) || [];
  return raw.map((o) => {
    if (o && typeof o === "object") {
      const obj = o as Record<string, unknown>;
      return { value: String(obj.value ?? obj.id ?? ""), label: String(obj.label ?? obj.value ?? "") };
    }
    // string choice → title-case label
    const v = String(o);
    return { value: v, label: v.charAt(0).toUpperCase() + v.slice(1).replace(/_/g, " ") };
  });
}
