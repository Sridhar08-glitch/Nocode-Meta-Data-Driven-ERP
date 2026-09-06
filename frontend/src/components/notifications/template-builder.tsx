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
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import {
  type NotificationTemplate,
  type TemplateChannel,
  TEMPLATE_CHANNEL_OPTIONS,
  renderPreview,
  templateVariables,
} from "@/lib/notifications/api";
import {
  useCreateTemplate,
  useDeleteTemplate,
  useTemplates,
  useTestTemplate,
  useUpdateTemplate,
} from "@/lib/notifications/hooks";
import { validateTemplate } from "@/lib/notifications/template-validation";
import { isValidSlug, slugify } from "@/lib/metadata/slug";

const channelLabel = (c: TemplateChannel) =>
  TEMPLATE_CHANNEL_OPTIONS.find((o) => o.value === c)?.label ?? c;

/**
 * Notification Template Builder (Phase F2.7): list + create/edit notification templates with a
 * `${var}` palette, client-side preview, and test-send. The backend render is authoritative —
 * the preview is only an editor aid. NotificationTemplate has no locale field (see report).
 */
export function TemplateBuilder() {
  const templates = useTemplates();
  const del = useDeleteTemplate();
  const [editing, setEditing] = useState<NotificationTemplate | null>(null);
  const [creating, setCreating] = useState(false);

  if (templates.isLoading) return <Skeleton className="h-64 w-full" />;
  if (templates.isError) return <ErrorState title="Couldn't load templates" />;
  const rows = templates.data ?? [];

  async function remove(t: NotificationTemplate) {
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
        <h2 className="text-sm font-medium text-muted-foreground">{rows.length} templates</h2>
        <Button size="sm" onClick={() => setCreating(true)}>
          New template
        </Button>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No templates"
          description="Author reusable notification content with ${variables}."
          action={{ label: "New template", onClick: () => setCreating(true) }}
        />
      ) : (
        <ul className="space-y-2">
          {rows.map((t) => (
            <li key={t.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{t.name}</span>
                <Badge variant="outline">{channelLabel(t.channel)}</Badge>
                <code className="text-xs text-muted-foreground">{t.slug}</code>
                {t.is_system && <Badge variant="secondary">system</Badge>}
              </span>
              <span className="flex shrink-0 items-center gap-1">
                <Button variant="ghost" size="sm" aria-label={`Edit template ${t.name}`} onClick={() => setEditing(t)}>
                  Edit
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Remove template ${t.name}`}
                  onClick={() => remove(t)}
                  disabled={del.isPending || t.is_system}
                >
                  Delete
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {creating && <TemplateDialog open onClose={() => setCreating(false)} />}
      {editing && <TemplateDialog open template={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function TemplateDialog({
  open,
  template,
  onClose,
}: {
  open: boolean;
  template?: NotificationTemplate;
  onClose: () => void;
}) {
  const isEdit = !!template;
  const create = useCreateTemplate();
  const update = useUpdateTemplate();
  const test = useTestTemplate();

  const [name, setName] = useState(template?.name ?? "");
  const [channel, setChannel] = useState<TemplateChannel>(template?.channel ?? "in_app");
  const [subject, setSubject] = useState(template?.subject_template ?? "");
  const [body, setBody] = useState(template?.body_template ?? "");
  const [previewJson, setPreviewJson] = useState("");

  // slug is editable only on create (it's the immutable key once persisted)
  const slug = isEdit ? template.slug : slugify(name);
  const vars = templateVariables(subject, body);
  const validation = validateTemplate([subject, body]);
  const valid = !!name.trim() && isValidSlug(slug) && !!body.trim() && validation.errors.length === 0;
  const pending = create.isPending || update.isPending;

  // preview context: detected vars default to "«var»", overridden by the user's sample JSON
  const defaultContext = Object.fromEntries(vars.map((v) => [v, `«${v}»`]));
  let userContext: Record<string, string> = {};
  let jsonError: string | null = null;
  if (previewJson.trim()) {
    try {
      const parsed: unknown = JSON.parse(previewJson);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        userContext = Object.fromEntries(Object.entries(parsed as Record<string, unknown>).map(([k, v]) => [k, String(v)]));
      } else {
        jsonError = "Sample data must be a JSON object.";
      }
    } catch {
      jsonError = "Invalid JSON.";
    }
  }
  const previewContext = { ...defaultContext, ...userContext };

  function insertVar(field: "subject" | "body", v: string) {
    const token = `\${${v}}`;
    if (field === "subject") setSubject((s) => s + token);
    else setBody((b) => b + token);
  }

  async function submit() {
    if (!valid) return;
    try {
      if (isEdit) {
        await update.mutateAsync({
          id: template.id,
          data: { name: name.trim(), channel, subject_template: subject, body_template: body },
        });
        toast.success("Template saved");
      } else {
        await create.mutateAsync({
          slug,
          name: name.trim(),
          channel,
          subject_template: subject,
          body_template: body,
        });
        toast.success("Template created");
      }
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save template");
    }
  }

  async function testSend() {
    if (!isEdit) return;
    try {
      const res = await test.mutateAsync({ id: template.id, context: previewContext });
      toast.success(`Test sent (${res.sent})`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not send test");
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit template" : "New template"}</DialogTitle>
        </DialogHeader>
        <div className="max-h-[65vh] space-y-4 overflow-y-auto">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="tpl-name">Name</Label>
              <Input id="tpl-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="tpl-channel">Channel</Label>
              <Select value={channel} onValueChange={(v) => setChannel(v as TemplateChannel)}>
                <SelectTrigger id="tpl-channel" className="w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TEMPLATE_CHANNEL_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="tpl-slug">Slug</Label>
              <Input id="tpl-slug" value={slug} readOnly disabled className="w-44 font-mono text-xs" />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tpl-subject">Subject</Label>
            <Input id="tpl-subject" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="New ${entity_label} assigned" />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tpl-body">Body</Label>
            <Textarea id="tpl-body" rows={5} value={body} onChange={(e) => setBody(e.target.value)} placeholder="Hi ${actor_name}, ..." />
          </div>

          <div className="space-y-1.5">
            <Label>Variables</Label>
            <div className="flex flex-wrap gap-1.5">
              {COMMON_VARS.map((v) => (
                <Button key={v} type="button" variant="outline" size="sm" className="h-7" aria-label={`Insert ${v} into body`} onClick={() => insertVar("body", v)}>
                  ${"{"}{v}{"}"}
                </Button>
              ))}
            </div>
            {vars.length > 0 && (
              <p className="text-xs text-muted-foreground">
                Detected: {vars.map((v) => `\${${v}}`).join(", ")}
              </p>
            )}
            {validation.errors.length > 0 && (
              <ul role="alert" className="space-y-0.5 text-xs text-destructive">
                {validation.errors.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tpl-preview-json">Preview sample data (JSON)</Label>
            <Textarea
              id="tpl-preview-json"
              rows={3}
              value={previewJson}
              onChange={(e) => setPreviewJson(e.target.value)}
              placeholder={'{ "customer_name": "John", "ticket_id": "INC-1001" }'}
              className="font-mono text-xs"
            />
            {jsonError && (
              <p role="alert" className="text-xs text-destructive">
                {jsonError}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label>Preview</Label>
            <div className="rounded-md border bg-muted/30 p-3 text-sm" aria-label="Template preview">
              {subject && <div className="font-medium">{renderPreview(subject, previewContext)}</div>}
              <div className="whitespace-pre-wrap text-muted-foreground">{renderPreview(body, previewContext) || "—"}</div>
            </div>
            <p className="text-xs text-muted-foreground">
              Preview is an editor aid only — the server renderer is authoritative on send.
            </p>
          </div>
        </div>
        <DialogFooter className="gap-2 sm:justify-between">
          <span>
            {isEdit && (
              <Button variant="outline" onClick={testSend} disabled={test.isPending} aria-label="Send test notification">
                {test.isPending ? "Sending…" : "Send test to me"}
              </Button>
            )}
          </span>
          <span className="flex gap-2">
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={!valid || pending}>
              {pending ? "Saving…" : isEdit ? "Save template" : "Create template"}
            </Button>
          </span>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Frequently-used render-context keys offered as one-click inserts. */
const COMMON_VARS = ["actor_name", "workspace_name", "record_title", "entity_label", "action_url"];
