"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/toast";
import { FormRenderer } from "@/features/form-renderer";
import { ApiError } from "@/lib/api/errors";
import { useCreateForm, useUpdateForm } from "@/lib/metadata/builder-hooks";
import {
  addFieldToSection,
  addSection,
  buildPreviewSchema,
  moveFieldWithinSection,
  moveSection,
  removeFieldFromSection,
  removeSection,
  unplacedFields,
  updateSection,
} from "@/lib/metadata/form-builder";
import type { FieldDef, FormDefinition, FormSection } from "@/lib/metadata/types";

export interface FormBuilderProps {
  entity: string;
  entityName: string;
  fields: FieldDef[];
  /** Existing form to edit; omit for a new form. */
  form?: FormDefinition;
  onSaved?: (form: FormDefinition) => void;
}

/** Form Builder (Phase F1.8): edit sections + field placement; live preview = Form Renderer. */
export function FormBuilder({ entity, entityName, fields, form, onSaved }: FormBuilderProps) {
  const [name, setName] = useState(form?.name ?? "Default");
  const [layoutType, setLayoutType] = useState<string>(
    (form?.settings?.layout_type as string) ?? "sections",
  );
  const [sections, setSections] = useState<FormSection[]>(
    form?.layout?.length ? form.layout : [{ key: "main", title: "Details", columns: 1, fields: [], condition: null }],
  );
  const create = useCreateForm(entity);
  const update = useUpdateForm(entity);

  const labelBySlug = new Map(fields.map((f) => [f.slug, f.name]));
  const available = unplacedFields(fields, sections);
  const preview = buildPreviewSchema({
    entitySlug: entity,
    entityName,
    fields,
    sections,
    layoutType,
  });

  async function save() {
    const settings = { ...(form?.settings ?? {}), layout_type: layoutType };
    try {
      const saved =
        form && form.id
          ? await update.mutateAsync({ formId: form.id, data: { name, layout: sections, settings } })
          : await create.mutateAsync({ name, layout: sections, settings, is_default: true });
      toast.success("Form saved");
      onSaved?.(saved);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save form");
    }
  }

  const pending = create.isPending || update.isPending;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="form-name">Form name</Label>
            <Input id="form-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="form-layout">Layout</Label>
            <Select value={layoutType} onValueChange={setLayoutType}>
              <SelectTrigger id="form-layout" className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="sections">Sections</SelectItem>
                <SelectItem value="wizard">Wizard</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button onClick={save} disabled={pending || !name.trim()}>
            {pending ? "Saving…" : "Save form"}
          </Button>
        </div>

        <div className="space-y-3">
          {sections.map((section, si) => (
            <div key={section.key} className="rounded-md border p-3">
              <div className="mb-2 flex items-center gap-2">
                <Input
                  aria-label={`Section ${si + 1} title`}
                  value={section.title}
                  onChange={(e) => setSections(updateSection(sections, si, { title: e.target.value }))}
                  className="h-8"
                />
                <Select
                  value={String(section.columns)}
                  onValueChange={(v) => setSections(updateSection(sections, si, { columns: Number(v) }))}
                >
                  <SelectTrigger aria-label="Columns" className="h-8 w-24">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">1 col</SelectItem>
                    <SelectItem value="2">2 cols</SelectItem>
                    <SelectItem value="3">3 cols</SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label="Move section up"
                  disabled={si === 0}
                  onClick={() => setSections(moveSection(sections, si, -1))}
                >
                  ↑
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label="Move section down"
                  disabled={si === sections.length - 1}
                  onClick={() => setSections(moveSection(sections, si, 1))}
                >
                  ↓
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label="Remove section"
                  onClick={() => setSections(removeSection(sections, si))}
                >
                  ✕
                </Button>
              </div>

              <ul className="space-y-1">
                {section.fields.map((slug, fi) => (
                  <li key={slug} className="flex items-center justify-between rounded bg-muted/40 px-2 py-1 text-sm">
                    <span>{labelBySlug.get(slug) ?? slug}</span>
                    <span className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label={`Move ${slug} up`}
                        disabled={fi === 0}
                        onClick={() => setSections(moveFieldWithinSection(sections, si, fi, -1))}
                      >
                        ↑
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label={`Move ${slug} down`}
                        disabled={fi === section.fields.length - 1}
                        onClick={() => setSections(moveFieldWithinSection(sections, si, fi, 1))}
                      >
                        ↓
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label={`Remove ${slug}`}
                        onClick={() => setSections(removeFieldFromSection(sections, si, slug))}
                      >
                        ✕
                      </Button>
                    </span>
                  </li>
                ))}
                {section.fields.length === 0 && (
                  <li className="px-2 py-1 text-xs text-muted-foreground">No fields yet.</li>
                )}
              </ul>

              {available.length > 0 && (
                <div className="mt-2">
                  <Select
                    value=""
                    onValueChange={(slug) => setSections(addFieldToSection(sections, si, slug))}
                  >
                    <SelectTrigger aria-label={`Add field to ${section.title}`} className="h-8">
                      <SelectValue placeholder="Add field…" />
                    </SelectTrigger>
                    <SelectContent>
                      {available.map((f) => (
                        <SelectItem key={f.slug} value={f.slug}>
                          {f.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={() => setSections(addSection(sections))}>
            Add section
          </Button>
        </div>
      </div>

      <div className="rounded-md border p-4">
        <h3 className="mb-3 text-sm font-medium text-muted-foreground">Live preview</h3>
        <FormRenderer schema={preview} onSubmit={() => undefined} submitLabel="Submit" disabled />
      </div>
    </div>
  );
}
