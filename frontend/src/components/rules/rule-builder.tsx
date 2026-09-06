"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { useEntities } from "@/lib/metadata/hooks";
import { isValidSlug, slugify } from "@/lib/metadata/slug";
import {
  type RuleAction,
  RULE_ACTION_OPTIONS,
  RULE_TRIGGER_OPTIONS,
  type RuleActionType,
  type RuleTrigger,
} from "@/lib/rules/api";
import { useCreateRule, useDeleteRule, useRules } from "@/lib/rules/hooks";

/** Rules Builder (Phase F2.4): NQL condition → action list, evaluated on record save. */
export function RuleBuilder() {
  const rules = useRules();
  const del = useDeleteRule();
  const [adding, setAdding] = useState(false);

  if (rules.isLoading) return <Skeleton className="h-64 w-full" />;
  if (rules.isError) return <ErrorState title="Couldn't load rules" />;
  const rows = rules.data?.results ?? [];

  async function remove(id: string) {
    try {
      await del.mutateAsync(id);
      toast.success("Rule removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove rule");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">{rows.length} rules</h2>
        <Button size="sm" onClick={() => setAdding(true)}>
          New rule
        </Button>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="No rules" description="Automate field changes and save-blocks." action={{ label: "New rule", onClick: () => setAdding(true) }} />
      ) : (
        <ul className="space-y-2">
          {rows.map((r) => (
            <li key={r.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{r.name}</span>
                <Badge variant="outline">{r.trigger_on}</Badge>
                {!r.is_active && <Badge variant="secondary">inactive</Badge>}
                <span className="text-xs text-muted-foreground">{r.actions.length} action(s) · priority {r.priority}</span>
              </span>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Remove rule ${r.name}`}
                onClick={() => remove(r.id)}
                disabled={del.isPending}
              >
                Delete
              </Button>
            </li>
          ))}
        </ul>
      )}
      {adding && <RuleDialog open onOpenChange={setAdding} />}
    </div>
  );
}

function RuleDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const entities = useEntities();
  const create = useCreateRule();
  const [name, setName] = useState("");
  const [entityId, setEntityId] = useState("");
  const [trigger, setTrigger] = useState<RuleTrigger>("before_update");
  const [condition, setCondition] = useState("");
  const [actions, setActions] = useState<RuleAction[]>([{ type: "set_field", field: "", value: "" }]);
  const [runAll, setRunAll] = useState(true);
  const slug = slugify(name);
  const valid = !!name.trim() && isValidSlug(slug) && !!entityId;

  const setAction = (i: number, patch: Partial<RuleAction>) =>
    setActions((a) => a.map((x, j) => (j === i ? { ...x, ...patch } : x)));

  async function submit() {
    if (!valid) return;
    try {
      await create.mutateAsync({
        name: name.trim(),
        slug,
        entity_id: entityId,
        trigger_on: trigger,
        condition_nql: condition.trim(),
        actions: actions.map((a) => (a.type === "block_save" ? { type: "block_save" } : a)),
        run_all: runAll,
      });
      toast.success("Rule created");
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create rule");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New rule</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="rule-name">Name</Label>
              <Input id="rule-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="rule-entity">Entity</Label>
              <Select value={entityId || undefined} onValueChange={setEntityId}>
                <SelectTrigger id="rule-entity" className="w-44">
                  <SelectValue placeholder="Pick entity" />
                </SelectTrigger>
                <SelectContent>
                  {(entities.data ?? []).map((e) => (
                    <SelectItem key={e.id} value={e.id}>
                      {e.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="rule-trigger">Trigger</Label>
              <Select value={trigger} onValueChange={(v) => setTrigger(v as RuleTrigger)}>
                <SelectTrigger id="rule-trigger" className="w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {RULE_TRIGGER_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="rule-cond">Condition (NQL — blank = always)</Label>
            <Input id="rule-cond" value={condition} onChange={(e) => setCondition(e.target.value)} placeholder="amount > 1000" />
          </div>
          <div className="space-y-2">
            <Label>Actions</Label>
            {actions.map((a, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2">
                <Select value={a.type} onValueChange={(v) => setAction(i, { type: v as RuleActionType })}>
                  <SelectTrigger aria-label={`Action ${i + 1} type`} className="h-8 w-36">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {RULE_ACTION_OPTIONS.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {a.type === "set_field" && (
                  <>
                    <Input aria-label={`Action ${i + 1} field`} className="h-8 w-32" placeholder="field" value={a.field ?? ""} onChange={(e) => setAction(i, { field: e.target.value })} />
                    <Input aria-label={`Action ${i + 1} value`} className="h-8 w-32" placeholder="value" value={String(a.value ?? "")} onChange={(e) => setAction(i, { value: e.target.value })} />
                  </>
                )}
                <Button variant="ghost" size="sm" aria-label={`Remove action ${i + 1}`} onClick={() => setActions((arr) => arr.filter((_, j) => j !== i))}>
                  ✕
                </Button>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={() => setActions((a) => [...a, { type: "set_field", field: "", value: "" }])}>
              Add action
            </Button>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={runAll} onCheckedChange={(v) => setRunAll(!!v)} /> Run all matching rules (don&apos;t stop at first)
          </label>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid || create.isPending}>
            {create.isPending ? "Creating…" : "Create rule"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
