"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { useEntities } from "@/lib/metadata/hooks";
import { useFields } from "@/lib/metadata/builder-hooks";
import {
  MASK_TYPE_OPTIONS,
  type MaskType,
} from "@/lib/permissions/api";
import {
  useCreateFieldPermission,
  useCreateMaskingRule,
  useDeleteFieldPermission,
  useDeleteMaskingRule,
  useFieldPermissions,
  useMaskingRules,
} from "@/lib/permissions/hooks";

/** Field-level read/write restrictions and data-masking rules for a role. */
export function FieldAccess({ roleId }: { roleId: string }) {
  const entities = useEntities();
  const [entitySlug, setEntitySlug] = useState<string>("");
  const fields = useFields(entitySlug);
  const [fieldId, setFieldId] = useState<string>("");

  const fps = useFieldPermissions(roleId);
  const masks = useMaskingRules(roleId);
  const createFp = useCreateFieldPermission();
  const delFp = useDeleteFieldPermission();
  const createMask = useCreateMaskingRule();
  const delMask = useDeleteMaskingRule();
  const [maskType, setMaskType] = useState<MaskType>("full");

  const fieldName = (id: string) =>
    (fields.data ?? []).find((f) => f.id === id)?.name ?? id;

  async function restrict(canRead: boolean, canWrite: boolean) {
    if (!fieldId) return;
    try {
      await createFp.mutateAsync({ field_id: fieldId, role_id: roleId, can_read: canRead, can_write: canWrite });
      toast.success("Field rule saved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save rule");
    }
  }

  async function addMask() {
    if (!fieldId) return;
    try {
      await createMask.mutateAsync({ field_id: fieldId, role_id: roleId, mask_type: maskType });
      toast.success("Masking rule saved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save rule");
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="fa-entity">Entity</Label>
          <Select
            value={entitySlug || undefined}
            onValueChange={(v) => {
              setEntitySlug(v);
              setFieldId("");
            }}
          >
            <SelectTrigger id="fa-entity" className="w-44">
              <SelectValue placeholder="Pick entity" />
            </SelectTrigger>
            <SelectContent>
              {(entities.data ?? []).map((e) => (
                <SelectItem key={e.id} value={e.slug}>
                  {e.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="fa-field">Field</Label>
          <Select value={fieldId || undefined} onValueChange={setFieldId} disabled={!entitySlug}>
            <SelectTrigger id="fa-field" className="w-44">
              <SelectValue placeholder="Pick field" />
            </SelectTrigger>
            <SelectContent>
              {(fields.data ?? []).map((f) => (
                <SelectItem key={f.id} value={f.id}>
                  {f.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button size="sm" variant="outline" disabled={!fieldId || createFp.isPending} onClick={() => restrict(false, false)}>
          Hide field
        </Button>
        <Button size="sm" variant="outline" disabled={!fieldId || createFp.isPending} onClick={() => restrict(true, false)}>
          Read-only
        </Button>
        <div className="flex items-end gap-2">
          <Select value={maskType} onValueChange={(v) => setMaskType(v as MaskType)}>
            <SelectTrigger aria-label="Mask type" className="h-9 w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MASK_TYPE_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" variant="outline" disabled={!fieldId || createMask.isPending} onClick={addMask}>
            Mask field
          </Button>
        </div>
      </div>

      <section className="space-y-2">
        <h3 className="text-sm font-medium text-muted-foreground">Field restrictions</h3>
        <ul className="space-y-1">
          {(fps.data ?? []).map((fp) => (
            <li key={fp.id} className="flex items-center justify-between rounded bg-muted/40 px-2 py-1 text-sm">
              <span className="flex items-center gap-2">
                <span className="font-mono text-xs">{fp.field_id}</span>
                <label className="flex items-center gap-1">
                  <Checkbox checked={fp.can_read} disabled /> read
                </label>
                <label className="flex items-center gap-1">
                  <Checkbox checked={fp.can_write} disabled /> write
                </label>
              </span>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Remove field rule ${fp.field_id}`}
                onClick={() => delFp.mutateAsync(fp.id)}
              >
                ✕
              </Button>
            </li>
          ))}
          {(fps.data ?? []).length === 0 && (
            <li className="px-2 py-1 text-xs text-muted-foreground">No field restrictions.</li>
          )}
        </ul>
      </section>

      <section className="space-y-2">
        <h3 className="text-sm font-medium text-muted-foreground">Masking rules</h3>
        <ul className="space-y-1">
          {(masks.data ?? []).map((m) => (
            <li key={m.id} className="flex items-center justify-between rounded bg-muted/40 px-2 py-1 text-sm">
              <span className="flex items-center gap-2">
                <span className="font-mono text-xs">{fieldName(m.field_id)}</span>
                <Badge variant="outline">{m.mask_type}</Badge>
              </span>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Remove mask ${m.field_id}`}
                onClick={() => delMask.mutateAsync(m.id)}
              >
                ✕
              </Button>
            </li>
          ))}
          {(masks.data ?? []).length === 0 && (
            <li className="px-2 py-1 text-xs text-muted-foreground">No masking rules.</li>
          )}
        </ul>
      </section>
    </div>
  );
}
