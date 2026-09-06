"use client";

import type { FieldInputKind } from "@/lib/metadata/field-types";

import { BooleanField } from "./boolean-field";
import type { FieldProps } from "./field-props";
import {
  DateField,
  FileField,
  JsonField,
  NumberInputField,
  ReadOnlyField,
  TextareaField,
  TextInputField,
} from "./inputs";
import { RelationField } from "./relation-field";
import { MultiSelectField, SelectField } from "./select-field";

/** Maps a field-type `kind` (from the registry) to its input component. */
export const FIELD_COMPONENTS: Record<FieldInputKind, React.ComponentType<FieldProps>> = {
  text: TextInputField,
  email: TextInputField,
  phone: TextInputField,
  url: TextInputField,
  location: TextInputField,
  barcode: TextInputField,
  textarea: TextareaField,
  richtext: TextareaField,
  number: NumberInputField,
  currency: NumberInputField,
  percent: NumberInputField,
  duration: NumberInputField,
  rating: NumberInputField,
  progress: NumberInputField,
  boolean: BooleanField,
  select: SelectField,
  multiselect: MultiSelectField,
  relation: RelationField,
  multirelation: RelationField,
  user: RelationField,
  multiuser: RelationField,
  date: DateField,
  datetime: DateField,
  time: DateField,
  file: FileField,
  image: FileField,
  json: JsonField,
  readonly: ReadOnlyField,
};

export function componentForKind(kind: FieldInputKind): React.ComponentType<FieldProps> {
  return FIELD_COMPONENTS[kind] ?? TextInputField;
}
