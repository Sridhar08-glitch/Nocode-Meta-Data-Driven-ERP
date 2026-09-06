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
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { EmailTemplate, RenderedEmail } from "@/lib/email-templates/api";
import {
  useCreateEmailTemplate,
  useDeleteEmailTemplate,
  useEmailTemplates,
  useRenderEmailTemplate,
  useTestSendEmailTemplate,
  useUpdateEmailTemplate,
} from "@/lib/email-templates/hooks";
import { isValidSlug, slugify } from "@/lib/metadata/slug";

/** Email Template Builder (Phase F3.6): locale-aware templates with server render + test-send. */
export function EmailTemplateBuilder() {
  const templates = useEmailTemplates();
  const del = useDeleteEmailTemplate();
  const [editing, setEditing] = useState<EmailTemplate | null>(null);
  const [creating, setCreating] = useState(false);

  const rows = templates.data?.results ?? [];

  async function remove(t: EmailTemplate) {
    try {
      await del.mutateAsync(t.id);
      toast.success("Template removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove template");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">{rows.length} email templates</h2>
        <Button size="sm" onClick={() => setCreating(true)}>
          New template
        </Button>
      </div>

      {templates.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : templates.isError ? (
        <ErrorState title="Couldn't load email templates" />
      ) : rows.length === 0 ? (
        <EmptyState title="No email templates" description="Author locale-aware email content rendered server-side." action={{ label: "New template", onClick: () => setCreating(true) }} />
      ) : (
        <ul className="space-y-2">
          {rows.map((t) => (
            <li key={t.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{t.name}</span>
                <code className="text-xs text-muted-foreground">{t.slug}</code>
                <Badge variant="outline">{t.locale}</Badge>
                <span className="text-xs text-muted-foreground">v{t.version}</span>
              </span>
              <span className="flex shrink-0 items-center gap-1">
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

      {creating && <TemplateDialog onClose={() => setCreating(false)} />}
      {editing && <TemplateDialog template={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function TemplateDialog({ template, onClose }: { template?: EmailTemplate; onClose: () => void }) {
  const isEdit = !!template;
  const create = useCreateEmailTemplate();
  const update = useUpdateEmailTemplate();
  const render = useRenderEmailTemplate();
  const testSend = useTestSendEmailTemplate();

  const [name, setName] = useState(template?.name ?? "");
  const [locale, setLocale] = useState(template?.locale ?? "en");
  const [subject, setSubject] = useState(template?.subject_template ?? "");
  const [body, setBody] = useState(template?.body_html ?? "");
  const [contextJson, setContextJson] = useState("");
  const [toEmail, setToEmail] = useState("");
  const [preview, setPreview] = useState<RenderedEmail | null>(null);

  const slug = isEdit ? template.slug : slugify(name);
  const valid = !!name.trim() && isValidSlug(slug) && !!locale.trim() && !!body.trim();
  const pending = create.isPending || update.isPending;

  function parseContext(): Record<string, unknown> {
    if (!contextJson.trim()) return {};
    try {
      const v: unknown = JSON.parse(contextJson);
      return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
    } catch {
      return {};
    }
  }

  async function submit() {
    if (!valid) return;
    try {
      if (isEdit) {
        await update.mutateAsync({ id: template.id, data: { name: name.trim(), locale: locale.trim(), subject_template: subject, body_html: body } });
        toast.success("Template saved");
      } else {
        await create.mutateAsync({ name: name.trim(), slug, locale: locale.trim(), subject_template: subject, body_html: body });
        toast.success("Template created");
      }
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save template");
    }
  }
  async function doPreview() {
    if (!isEdit) return;
    try {
      const r = await render.mutateAsync({ id: template.id, context: parseContext() });
      setPreview(r);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Render failed");
    }
  }
  async function doTestSend() {
    if (!isEdit || !toEmail.trim()) return;
    try {
      await testSend.mutateAsync({ id: template.id, toEmail: toEmail.trim(), context: parseContext() });
      toast.success("Test email sent");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Test send failed");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit email template" : "New email template"}</DialogTitle>
        </DialogHeader>
        <div className="max-h-[65vh] space-y-4 overflow-y-auto">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="et-name">Name</Label>
              <Input id="et-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="et-locale">Locale</Label>
              <Input id="et-locale" value={locale} onChange={(e) => setLocale(e.target.value)} placeholder="en, fr-FR" className="w-28" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="et-slug">Slug</Label>
              <Input id="et-slug" value={slug} readOnly disabled className="w-40 font-mono text-xs" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="et-subject">Subject</Label>
            <Input id="et-subject" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Welcome, ${name}" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="et-body">Body (HTML, sanitized server-side)</Label>
            <Textarea id="et-body" rows={6} value={body} onChange={(e) => setBody(e.target.value)} className="font-mono text-xs" />
          </div>

          {isEdit ? (
            <div className="space-y-3 rounded-md border p-3">
              <div className="space-y-1.5">
                <Label htmlFor="et-ctx">Sample context (JSON)</Label>
                <Textarea id="et-ctx" rows={2} value={contextJson} onChange={(e) => setContextJson(e.target.value)} placeholder={'{ "name": "Ada" }'} className="font-mono text-xs" />
              </div>
              <div className="flex flex-wrap items-end gap-2">
                <Button type="button" variant="outline" onClick={doPreview} disabled={render.isPending} aria-label="Render preview">
                  {render.isPending ? "Rendering…" : "Render preview"}
                </Button>
                <div className="space-y-1.5">
                  <Label htmlFor="et-to">Test recipient</Label>
                  <Input id="et-to" type="email" value={toEmail} onChange={(e) => setToEmail(e.target.value)} className="w-56" />
                </div>
                <Button type="button" variant="outline" onClick={doTestSend} disabled={!toEmail.trim() || testSend.isPending} aria-label="Send test email">
                  {testSend.isPending ? "Sending…" : "Send test"}
                </Button>
              </div>
              {preview && (
                <div className="space-y-1.5">
                  <p className="text-sm font-medium">{preview.subject}</p>
                  <iframe aria-label="Email preview" title="Email preview" srcDoc={preview.html} className="h-48 w-full rounded border bg-white" sandbox="" />
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">Save the template to render a preview or send a test.</p>
          )}
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
