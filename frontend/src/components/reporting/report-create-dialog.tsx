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
import { REPORT_TYPE_OPTIONS, type ReportType } from "@/lib/reporting/api";
import { useCreateReport, useValidateNql } from "@/lib/reporting/hooks";

/** Create a report (name + type + NQL); validates the NQL before saving. */
export function ReportCreateDialog({ onCreated }: { onCreated?: (id: string) => void }) {
  const create = useCreateReport();
  const validate = useValidateNql();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState<ReportType>("table");
  const [nql, setNql] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const slug = slugify(name);
  const valid = !!name.trim() && isValidSlug(slug);

  async function submit() {
    if (!valid) return;
    setErrors([]);
    try {
      if (nql.trim()) {
        const res = await validate.mutateAsync({ nql_source: nql.trim() });
        if (!res.valid) {
          setErrors(res.errors);
          return;
        }
      }
      const report = await create.mutateAsync({
        name: name.trim(),
        slug,
        report_type: type,
        nql_source: nql.trim(),
        nql_ast: {},
      });
      toast.success(`Created “${report.name}”`);
      setOpen(false);
      setName("");
      setNql("");
      onCreated?.(report.id);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create report");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>New report</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New report</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="report-name">Name</Label>
            <Input id="report-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="report-type">Type</Label>
            <Select value={type} onValueChange={(v) => setType(v as ReportType)}>
              <SelectTrigger id="report-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {REPORT_TYPE_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="report-nql">NQL (optional)</Label>
            <Input id="report-nql" value={nql} onChange={(e) => setNql(e.target.value)} placeholder="status = 'open'" />
            {errors.length > 0 && (
              <ul className="list-inside list-disc text-xs text-destructive" role="alert">
                {errors.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid || create.isPending || validate.isPending}>
            {create.isPending || validate.isPending ? "Saving…" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
