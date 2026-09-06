"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { useCreateField, useUpdateField } from "@/lib/metadata/builder-hooks";
import { FIELD_TYPE_GROUPS, isValidSlug, slugify } from "@/lib/metadata/slug";
import type { FieldCreate, FieldDef } from "@/lib/metadata/types";

const CHOICE_TYPES = new Set(["select", "status", "multi_select"]);
const COMPUTED_TYPES = new Set(["formula", "rollup", "count", "auto_number"]);

export interface FieldDialogProps {
  entity: string;
  /** Provide to edit; omit to create. */
  field?: FieldDef;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Field Builder — create or edit a single field, including type-specific config. */
export function FieldDialog({ entity, field, open, onOpenChange }: FieldDialogProps) {
  const editing = !!field;
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [fieldType, setFieldType] = useState("text");
  const [required, setRequired] = useState(false);
  const [unique, setUnique] = useState(false);
  const [promoted, setPromoted] = useState(true);
  const [options, setOptions] = useState(""); // comma-separated for choice types
  const [formula, setFormula] = useState("");

  const create = useCreateField(entity);
  const update = useUpdateField(entity);

  useEffect(() => {
    if (!open) return;
    if (field) {
      setName(field.name);
      setSlug(field.slug);
      setFieldType(field.field_type);
      setRequired(field.is_required);
      setUnique(field.is_unique);
      setPromoted(field.is_promoted);
      const cfgOptions = Array.isArray(field.config?.options) ? field.config.options : [];
      setOptions((cfgOptions as { label?: string; value?: string }[]).map(optLabel).join(", "));
      setFormula(typeof field.config?.expression === "string" ? field.config.expression : "");
    } else {
      setName("");
      setSlug("");
      setSlugTouched(false);
      setFieldType("text");
      setRequired(false);
      setUnique(false);
      setPromoted(true);
      setOptions("");
      setFormula("");
    }
  }, [open, field]);

  const effectiveSlug = editing ? slug : slugTouched ? slug : slugify(name);
  const slugOk = isValidSlug(effectiveSlug);

  function buildConfig(): Record<string, unknown> {
    if (CHOICE_TYPES.has(fieldType)) {
      const opts = options
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map((v) => ({ label: v, value: slugify(v) || v }));
      return { options: opts };
    }
    if (fieldType === "formula") return { expression: formula };
    return {};
  }

  async function submit() {
    if (!name.trim() || !slugOk) return;
    const config = buildConfig();
    try {
      if (editing && field) {
        await update.mutateAsync({
          fieldSlug: field.slug,
          data: { name: name.trim(), is_required: required, is_unique: unique, config },
        });
        toast.success("Field updated");
      } else {
        const body: FieldCreate = {
          slug: effectiveSlug,
          name: name.trim(),
          field_type: fieldType,
          is_required: required,
          is_unique: unique,
          is_promoted: promoted,
          config,
        };
        await create.mutateAsync(body);
        toast.success("Field added");
      }
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save field");
    }
  }

  const pending = create.isPending || update.isPending;
  const isComputed = COMPUTED_TYPES.has(fieldType);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{editing ? `Edit “${field?.name}”` : "Add field"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="field-name">Label</Label>
            <Input
              id="field-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
          </div>
          {!editing && (
            <div className="space-y-1.5">
              <Label htmlFor="field-slug">Slug</Label>
              <Input
                id="field-slug"
                value={effectiveSlug}
                onChange={(e) => {
                  setSlugTouched(true);
                  setSlug(e.target.value);
                }}
                aria-invalid={!slugOk}
              />
              {!slugOk && effectiveSlug !== "" && (
                <p className="text-xs text-destructive" role="alert">
                  Lowercase letters, digits, underscores; must start with a letter.
                </p>
              )}
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="field-type">Type</Label>
            <Select value={fieldType} onValueChange={setFieldType} disabled={editing}>
              <SelectTrigger id="field-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FIELD_TYPE_GROUPS.map((g) => (
                  <SelectGroup key={g.group}>
                    <SelectLabel>{g.group}</SelectLabel>
                    {g.types.map((t) => (
                      <SelectItem key={t.value} value={t.value}>
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                ))}
              </SelectContent>
            </Select>
            {editing && (
              <p className="text-xs text-muted-foreground">Type can’t change after creation.</p>
            )}
          </div>

          {CHOICE_TYPES.has(fieldType) && (
            <div className="space-y-1.5">
              <Label htmlFor="field-options">Options (comma-separated)</Label>
              <Input
                id="field-options"
                value={options}
                onChange={(e) => setOptions(e.target.value)}
                placeholder="Open, In progress, Closed"
              />
            </div>
          )}
          {fieldType === "formula" && (
            <div className="space-y-1.5">
              <Label htmlFor="field-formula">Formula expression</Label>
              <Input
                id="field-formula"
                value={formula}
                onChange={(e) => setFormula(e.target.value)}
                placeholder="amount * 1.2"
              />
            </div>
          )}

          {!isComputed && (
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={required} onCheckedChange={(v) => setRequired(!!v)} /> Required
              </label>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={unique} onCheckedChange={(v) => setUnique(!!v)} /> Unique
              </label>
              {!editing && (
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox checked={promoted} onCheckedChange={(v) => setPromoted(!!v)} /> Real
                  column
                </label>
              )}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!name.trim() || !slugOk || pending}>
            {pending ? "Saving…" : editing ? "Save" : "Add field"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function optLabel(o: { label?: string; value?: string }): string {
  return o.label ?? o.value ?? "";
}
