"use client";

import { useRouter } from "next/navigation";
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
import { ApiError } from "@/lib/api/errors";
import { useEntities } from "@/lib/metadata/hooks";
import { DUPLICATE_STRATEGY_OPTIONS, type DuplicateStrategy } from "@/lib/staging/api";
import { useCreateImport } from "@/lib/staging/hooks";

export default function ImportPage() {
  const router = useRouter();
  const entities = useEntities();
  const create = useCreateImport();
  const [entitySlug, setEntitySlug] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [strategy, setStrategy] = useState<DuplicateStrategy>("skip");

  async function upload() {
    if (!file || !entitySlug) return;
    try {
      const job = await create.mutateAsync({ file, entity_slug: entitySlug, duplicate_strategy: strategy });
      router.push(`/import/${job.id}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Upload failed");
    }
  }

  return (
    <div className="max-w-lg space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Import data</h1>
        <p className="text-sm text-muted-foreground">Upload a CSV or XLSX file; we&apos;ll validate before importing.</p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="imp-entity">Entity</Label>
        <Select value={entitySlug || undefined} onValueChange={setEntitySlug}>
          <SelectTrigger id="imp-entity">
            <SelectValue placeholder="Pick an entity" />
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
        <Label htmlFor="imp-file">File</Label>
        <Input id="imp-file" type="file" accept=".csv,.xlsx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="imp-dup">Duplicates</Label>
        <Select value={strategy} onValueChange={(v) => setStrategy(v as DuplicateStrategy)}>
          <SelectTrigger id="imp-dup">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DUPLICATE_STRATEGY_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Button onClick={upload} disabled={!file || !entitySlug || create.isPending}>
        {create.isPending ? "Uploading…" : "Upload &amp; validate"}
      </Button>
    </div>
  );
}
