"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { useCreateEntity } from "@/lib/metadata/builder-hooks";
import { isValidSlug, slugify } from "@/lib/metadata/slug";

/** Entity Builder — create a new entity. On success, calls `onCreated(slug)`. */
export function EntityCreateDialog({ onCreated }: { onCreated?: (slug: string) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [pluralName, setPluralName] = useState("");
  const [description, setDescription] = useState("");
  const create = useCreateEntity();

  const effectiveSlug = slugTouched ? slug : slugify(name);
  const slugOk = isValidSlug(effectiveSlug);

  function reset() {
    setName("");
    setSlug("");
    setSlugTouched(false);
    setPluralName("");
    setDescription("");
  }

  async function submit() {
    if (!name.trim() || !slugOk) return;
    try {
      const entity = await create.mutateAsync({
        slug: effectiveSlug,
        name: name.trim(),
        plural_name: pluralName.trim() || `${name.trim()}s`,
        description: description.trim(),
      });
      toast.success(`Created “${entity.name}”`);
      setOpen(false);
      reset();
      onCreated?.(entity.slug);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create entity");
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button>New entity</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New entity</DialogTitle>
          <DialogDescription>
            A new metadata-driven object. A physical table is created automatically.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="entity-name">Name</Label>
            <Input
              id="entity-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Lead"
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="entity-slug">Slug</Label>
            <Input
              id="entity-slug"
              value={effectiveSlug}
              onChange={(e) => {
                setSlugTouched(true);
                setSlug(e.target.value);
              }}
              placeholder="lead"
              aria-invalid={!slugOk}
            />
            {!slugOk && effectiveSlug !== "" && (
              <p className="text-xs text-destructive" role="alert">
                Lowercase letters, digits, and underscores; must start with a letter.
              </p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="entity-plural">Plural name</Label>
            <Input
              id="entity-plural"
              value={pluralName}
              onChange={(e) => setPluralName(e.target.value)}
              placeholder="Leads"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="entity-desc">Description</Label>
            <Input
              id="entity-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!name.trim() || !slugOk || create.isPending}>
            {create.isPending ? "Creating…" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
