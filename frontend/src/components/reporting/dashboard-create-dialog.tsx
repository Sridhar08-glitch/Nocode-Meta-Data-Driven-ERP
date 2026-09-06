"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { isValidSlug, slugify } from "@/lib/metadata/slug";
import { useCreateDashboard } from "@/lib/reporting/hooks";

/** Create a dashboard (name → derived slug). */
export function DashboardCreateDialog({ onCreated }: { onCreated?: (id: string) => void }) {
  const create = useCreateDashboard();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const slug = slugify(name);
  const valid = !!name.trim() && isValidSlug(slug);

  async function submit() {
    if (!valid) return;
    try {
      const d = await create.mutateAsync({ name: name.trim(), slug });
      toast.success(`Created “${d.name}”`);
      setOpen(false);
      setName("");
      onCreated?.(d.id);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create dashboard");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>New dashboard</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New dashboard</DialogTitle>
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="dash-name">Name</Label>
          <Input id="dash-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid || create.isPending}>
            {create.isPending ? "Creating…" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
