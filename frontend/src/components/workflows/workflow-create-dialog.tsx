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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { isValidSlug, slugify } from "@/lib/metadata/slug";
import { TRIGGER_TYPE_OPTIONS, type TriggerType } from "@/lib/workflows/api";
import { useCreateWorkflow } from "@/lib/workflows/hooks";

/** Create a workflow definition (name + trigger). On success calls `onCreated(id)`. */
export function WorkflowCreateDialog({ onCreated }: { onCreated?: (id: string) => void }) {
  const create = useCreateWorkflow();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState<TriggerType>("record_created");
  const slug = slugify(name);
  const valid = !!name.trim() && isValidSlug(slug);

  async function submit() {
    if (!valid) return;
    try {
      const wf = await create.mutateAsync({ name: name.trim(), slug, trigger_type: trigger });
      toast.success(`Created “${wf.name}”`);
      setOpen(false);
      setName("");
      onCreated?.(wf.id);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create workflow");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>New workflow</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New workflow</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="wf-name">Name</Label>
            <Input id="wf-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="wf-trigger-type">Trigger</Label>
            <Select value={trigger} onValueChange={(v) => setTrigger(v as TriggerType)}>
              <SelectTrigger id="wf-trigger-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TRIGGER_TYPE_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
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
