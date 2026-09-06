"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { builderApi } from "@/lib/metadata/builder-api";
import { useDeleteEntity, useUpdateEntity } from "@/lib/metadata/builder-hooks";
import type { EntityMeta } from "@/lib/metadata/types";

import { ImpactWarningDialog } from "./impact-warning-dialog";

export function EntitySettings({ entity }: { entity: EntityMeta }) {
  const router = useRouter();
  const [name, setName] = useState(entity.name);
  const [pluralName, setPluralName] = useState(entity.plural_name);
  const [description, setDescription] = useState(entity.description);
  const [icon, setIcon] = useState(entity.icon);
  const [color, setColor] = useState(entity.color);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const update = useUpdateEntity(entity.slug);
  const archive = useDeleteEntity();

  const dirty =
    name !== entity.name ||
    pluralName !== entity.plural_name ||
    description !== entity.description ||
    icon !== entity.icon ||
    color !== entity.color;

  async function save() {
    try {
      await update.mutateAsync({
        name: name.trim(),
        plural_name: pluralName.trim(),
        description,
        icon,
        color,
      });
      toast.success("Entity updated");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save");
    }
  }

  async function doArchive() {
    try {
      await archive.mutateAsync(entity.slug);
      toast.success(`Archived “${entity.name}”`);
      setConfirmArchive(false);
      router.push("/studio");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not archive");
    }
  }

  return (
    <div className="max-w-lg space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="set-name">Name</Label>
          <Input id="set-name" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="set-plural">Plural</Label>
          <Input id="set-plural" value={pluralName} onChange={(e) => setPluralName(e.target.value)} />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="set-desc">Description</Label>
        <Input id="set-desc" value={description} onChange={(e) => setDescription(e.target.value)} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="set-icon">Icon</Label>
          <Input id="set-icon" value={icon} onChange={(e) => setIcon(e.target.value)} placeholder="box" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="set-color">Color</Label>
          <Input id="set-color" value={color} onChange={(e) => setColor(e.target.value)} placeholder="#2563eb" />
        </div>
      </div>
      <div className="flex items-center justify-between pt-2">
        <Button onClick={save} disabled={!dirty || !name.trim() || update.isPending}>
          {update.isPending ? "Saving…" : "Save settings"}
        </Button>
        <Button variant="destructive" onClick={() => setConfirmArchive(true)}>
          Archive entity
        </Button>
      </div>

      {confirmArchive && (
        <ImpactWarningDialog
        open
        title={`Archive “${entity.name}”?`}
        note="The entity is hidden but its data and table are preserved — you can restore it later."
        queryKey={["impact", "entity", entity.slug]}
        fetcher={() => builderApi.entityImpact(entity.slug)}
        confirmLabel="Archive"
        busyLabel="Archiving…"
        busy={archive.isPending}
        onCancel={() => setConfirmArchive(false)}
        onConfirm={doArchive}
        />
      )}
    </div>
  );
}
