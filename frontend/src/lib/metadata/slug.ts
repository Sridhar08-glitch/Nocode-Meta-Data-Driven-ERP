/** Slugify a label into a backend-valid entity/field slug: `^[a-z][a-z0-9_]{0,62}$`. */
export function slugify(input: string): string {
  const base = input
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/_{2,}/g, "_");
  const prefixed = /^[a-z]/.test(base) ? base : `f_${base}`;
  return prefixed.slice(0, 63);
}

export const SLUG_PATTERN = /^[a-z][a-z0-9_]{0,62}$/;

export function isValidSlug(slug: string): boolean {
  return SLUG_PATTERN.test(slug);
}

/** Field types offered in the Field Builder picker, grouped for the UI. */
export const FIELD_TYPE_GROUPS: { group: string; types: { value: string; label: string }[] }[] = [
  {
    group: "Text",
    types: [
      { value: "text", label: "Text" },
      { value: "textarea", label: "Long text" },
      { value: "rich_text", label: "Rich text" },
      { value: "email", label: "Email" },
      { value: "phone", label: "Phone" },
      { value: "url", label: "URL" },
      { value: "barcode", label: "Barcode" },
    ],
  },
  {
    group: "Number",
    types: [
      { value: "integer", label: "Integer" },
      { value: "decimal", label: "Decimal" },
      { value: "currency", label: "Currency" },
      { value: "percent", label: "Percent" },
      { value: "duration", label: "Duration" },
      { value: "rating", label: "Rating" },
      { value: "progress", label: "Progress" },
    ],
  },
  {
    group: "Date & time",
    types: [
      { value: "date", label: "Date" },
      { value: "datetime", label: "Date & time" },
      { value: "time", label: "Time" },
    ],
  },
  {
    group: "Choice",
    types: [
      { value: "boolean", label: "Checkbox" },
      { value: "select", label: "Select" },
      { value: "status", label: "Status" },
      { value: "multi_select", label: "Multi-select" },
    ],
  },
  {
    group: "Relational",
    types: [
      { value: "lookup", label: "Lookup" },
      { value: "multi_lookup", label: "Multi-lookup" },
      { value: "user", label: "User" },
      { value: "multi_user", label: "Multi-user" },
    ],
  },
  {
    group: "Files",
    types: [
      { value: "file", label: "File" },
      { value: "image", label: "Image" },
    ],
  },
  {
    group: "Computed (read-only)",
    types: [
      { value: "formula", label: "Formula" },
      { value: "rollup", label: "Rollup" },
      { value: "count", label: "Count" },
      { value: "auto_number", label: "Auto number" },
    ],
  },
  {
    group: "Other",
    types: [
      { value: "json", label: "JSON" },
      { value: "location", label: "Location" },
    ],
  },
];

/** Flat field-type value → label map for display. */
export const FIELD_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  FIELD_TYPE_GROUPS.flatMap((g) => g.types).map((t) => [t.value, t.label]),
);
