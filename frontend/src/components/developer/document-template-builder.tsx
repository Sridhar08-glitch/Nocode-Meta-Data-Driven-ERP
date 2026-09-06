"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { DocBlock, DocumentTemplate } from "@/lib/document-templates/api";
import {
  useCreateDocTemplate,
  useDeleteDocTemplate,
  useDocumentTemplates,
  useRenderDocPdf,
  useUpdateDocTemplate,
} from "@/lib/document-templates/hooks";
import { useEntities } from "@/lib/metadata/hooks";
import { isValidSlug, slugify } from "@/lib/metadata/slug";

/** Document/PDF Template Builder (Phase F3.6): entity-bound templates rendered to PDF server-side. */
export function DocumentTemplateBuilder() {
  const templates = useDocumentTemplates();
  const del = useDeleteDocTemplate();
  const render = useRenderDocPdf();
  const [editing, setEditing] = useState<DocumentTemplate | null>(null);
  const [creating, setCreating] = useState(false);
  const [renderFor, setRenderFor] = useState<DocumentTemplate | null>(null);
  const [recordId, setRecordId] = useState("");

  const rows = templates.data?.results ?? [];

  async function remove(t: DocumentTemplate) {
    try {
      await del.mutateAsync(t.id);
      toast.success("Template removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove template");
    }
  }
  async function doRender() {
    if (!renderFor || !recordId.trim()) return;
    try {
      await render.mutateAsync({ id: renderFor.id, recordId: recordId.trim(), filename: `${renderFor.slug}.pdf` });
      toast.success("PDF generated");
      setRenderFor(null);
      setRecordId("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not render PDF");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">{rows.length} document templates</h2>
        <Button size="sm" onClick={() => setCreating(true)}>
          New template
        </Button>
      </div>

      {templates.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : templates.isError ? (
        <ErrorState title="Couldn't load document templates" />
      ) : rows.length === 0 ? (
        <EmptyState title="No document templates" description="Bind a template to an entity and render records to PDF." action={{ label: "New template", onClick: () => setCreating(true) }} />
      ) : (
        <ul className="space-y-2">
          {rows.map((t) => (
            <li key={t.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{t.name}</span>
                <Badge variant="outline">{t.entity_slug}</Badge>
                <span className="text-xs text-muted-foreground">{t.blocks.length} field(s) · v{t.version}</span>
              </span>
              <span className="flex shrink-0 items-center gap-1">
                <Button variant="ghost" size="sm" aria-label={`Render ${t.name}`} onClick={() => setRenderFor(t)}>
                  Render PDF
                </Button>
                <Button variant="ghost" size="sm" aria-label={`Edit ${t.name}`} onClick={() => setEditing(t)}>
                  Edit
                </Button>
                <Button variant="ghost" size="sm" aria-label={`Remove ${t.name}`} onClick={() => remove(t)} disabled={del.isPending}>
                  Delete
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {creating && <DocDialog onClose={() => setCreating(false)} />}
      {editing && <DocDialog template={editing} onClose={() => setEditing(null)} />}

      <Dialog open={!!renderFor} onOpenChange={(o) => !o && setRenderFor(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Render {renderFor?.name} to PDF</DialogTitle>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="dt-record">Record ID ({renderFor?.entity_slug})</Label>
            <Input id="dt-record" value={recordId} onChange={(e) => setRecordId(e.target.value)} className="font-mono text-xs" autoFocus />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRenderFor(null)}>
              Cancel
            </Button>
            <Button onClick={doRender} disabled={!recordId.trim() || render.isPending}>
              {render.isPending ? "Rendering…" : "Download PDF"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function DocDialog({ template, onClose }: { template?: DocumentTemplate; onClose: () => void }) {
  const isEdit = !!template;
  const entities = useEntities();
  const create = useCreateDocTemplate();
  const update = useUpdateDocTemplate();

  const [name, setName] = useState(template?.name ?? "");
  const [entitySlug, setEntitySlug] = useState(template?.entity_slug ?? "");
  const [title, setTitle] = useState(template?.page_config?.title ?? "");
  const [subtitle, setSubtitle] = useState(template?.page_config?.subtitle ?? "");
  const [blocks, setBlocks] = useState<DocBlock[]>(template?.blocks ?? [{ field: "", label: "" }]);
  const [relField, setRelField] = useState(template?.line_items?.relation_field ?? "");
  const [relEntity, setRelEntity] = useState(template?.line_items?.entity_slug ?? "");
  const [columns, setColumns] = useState((template?.line_items?.columns ?? []).join(", "));

  const slug = isEdit ? template.slug : slugify(name);
  const valid = !!name.trim() && isValidSlug(slug) && !!entitySlug;
  const pending = create.isPending || update.isPending;

  const patchBlock = (i: number, p: Partial<DocBlock>) => setBlocks((b) => b.map((x, j) => (j === i ? { ...x, ...p } : x)));

  async function submit() {
    if (!valid) return;
    const colList = columns.split(",").map((c) => c.trim()).filter(Boolean);
    const data = {
      name: name.trim(),
      entity_slug: entitySlug,
      page_config: { title: title.trim(), subtitle: subtitle.trim() },
      blocks: blocks.filter((b) => b.field.trim()).map((b) => ({ field: b.field.trim(), label: b.label?.trim() || undefined })),
      line_items: relField.trim() && relEntity.trim() && colList.length > 0 ? { entity_slug: relEntity.trim(), relation_field: relField.trim(), columns: colList } : {},
    };
    try {
      if (isEdit) {
        await update.mutateAsync({ id: template.id, data });
        toast.success("Template saved");
      } else {
        await create.mutateAsync({ slug, ...data });
        toast.success("Template created");
      }
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save template");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit document template" : "New document template"}</DialogTitle>
        </DialogHeader>
        <div className="max-h-[65vh] space-y-4 overflow-y-auto">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="dc-name">Name</Label>
              <Input id="dc-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="dc-entity">Bound entity</Label>
              <Select value={entitySlug || undefined} onValueChange={setEntitySlug} disabled={isEdit}>
                <SelectTrigger id="dc-entity" className="w-48">
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
          </div>

          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="dc-title">Document title</Label>
              <Input id="dc-title" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="dc-subtitle">Subtitle</Label>
              <Input id="dc-subtitle" value={subtitle} onChange={(e) => setSubtitle(e.target.value)} />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Header fields</Label>
            {blocks.map((b, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2">
                <Input aria-label={`Field ${i + 1} slug`} className="h-8 w-40" placeholder="field slug" value={b.field} onChange={(e) => patchBlock(i, { field: e.target.value })} />
                <Input aria-label={`Field ${i + 1} label`} className="h-8 w-40" placeholder="label (optional)" value={b.label ?? ""} onChange={(e) => patchBlock(i, { label: e.target.value })} />
                <Button variant="ghost" size="sm" aria-label={`Remove field ${i + 1}`} onClick={() => setBlocks((arr) => arr.filter((_, j) => j !== i))}>
                  ✕
                </Button>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={() => setBlocks((b) => [...b, { field: "", label: "" }])}>
              Add field
            </Button>
          </div>

          <div className="space-y-2 rounded-md border p-3">
            <Label>Line items (optional)</Label>
            <div className="flex flex-wrap items-center gap-2">
              <Input aria-label="Line items entity slug" className="h-8 w-40" placeholder="related entity slug" value={relEntity} onChange={(e) => setRelEntity(e.target.value)} />
              <Input aria-label="Line items relation field" className="h-8 w-40" placeholder="relation field" value={relField} onChange={(e) => setRelField(e.target.value)} />
            </div>
            <Input aria-label="Line items columns" placeholder="columns, comma-separated" value={columns} onChange={(e) => setColumns(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid || pending}>
            {pending ? "Saving…" : isEdit ? "Save template" : "Create template"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
