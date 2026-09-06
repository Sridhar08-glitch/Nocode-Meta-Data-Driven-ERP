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
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import {
  ON_ERROR_OPTIONS,
  STEP_TYPE_OPTIONS,
  TRIGGER_TYPE_OPTIONS,
  type StepErrorMode,
  type TriggerType,
  type WorkflowStep,
} from "@/lib/workflows/api";
import {
  useCreateEdge,
  useCreateStep,
  useDeleteEdge,
  useDeleteStep,
  useSetWorkflowStatus,
  useUpdateWorkflow,
  useWorkflowDefinition,
  useWorkflowEdges,
  useWorkflowSteps,
} from "@/lib/workflows/hooks";
import { cn } from "@/lib/utils";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  active: "default",
  paused: "secondary",
  draft: "outline",
  archived: "destructive",
};

const stepLabel = (type: string) =>
  STEP_TYPE_OPTIONS.find((s) => s.value === type)?.label ?? type;

/** Deterministic workflow designer (Phase F1.10): trigger + steps (nodes) + edges (connections). */
export function WorkflowDesigner({ definitionId }: { definitionId: string }) {
  const def = useWorkflowDefinition(definitionId);
  const steps = useWorkflowSteps(definitionId);
  const edges = useWorkflowEdges(definitionId);
  const updateWf = useUpdateWorkflow();
  const setStatus = useSetWorkflowStatus();
  const delStep = useDeleteStep(definitionId);
  const delEdge = useDeleteEdge(definitionId);
  const [addingStep, setAddingStep] = useState(false);
  const [connecting, setConnecting] = useState(false);

  if (def.isLoading) return <Skeleton className="h-64 w-full" />;
  if (def.isError || !def.data) return <ErrorState title="Couldn't load workflow" />;

  const wf = def.data;
  const stepRows = steps.data?.results ?? [];
  const edgeRows = edges.data?.results ?? [];
  const stepName = (id: string) => stepRows.find((s) => s.id === id)?.name ?? id;
  const active = wf.status === "active";

  async function changeTrigger(trigger_type: TriggerType) {
    try {
      await updateWf.mutateAsync({ id: definitionId, data: { trigger_type } });
      toast.success("Trigger updated");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not update trigger");
    }
  }

  async function toggleActive() {
    try {
      await setStatus.mutateAsync({ id: definitionId, action: active ? "pause" : "activate" });
      toast.success(active ? "Workflow paused" : "Workflow activated");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not change status");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">{wf.name}</h2>
          <Badge variant={STATUS_VARIANT[wf.status]}>{wf.status}</Badge>
        </div>
        <Button onClick={toggleActive} disabled={setStatus.isPending}>
          {active ? "Pause" : "Activate"}
        </Button>
      </div>

      <section className="space-y-2">
        <Label htmlFor="wf-trigger">Trigger</Label>
        <Select value={wf.trigger_type} onValueChange={(v) => changeTrigger(v as TriggerType)}>
          <SelectTrigger id="wf-trigger" className="w-64">
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
      </section>

      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-muted-foreground">{stepRows.length} steps</h3>
          <Button size="sm" onClick={() => setAddingStep(true)}>
            Add step
          </Button>
        </div>
        {stepRows.length === 0 ? (
          <EmptyState
            title="No steps"
            description="Add the first action or condition."
            action={{ label: "Add step", onClick: () => setAddingStep(true) }}
          />
        ) : (
          <ul className="space-y-2">
            {stepRows.map((s) => (
              <li
                key={s.id}
                className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm"
              >
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{s.name}</span>
                  <Badge variant="outline">{stepLabel(s.step_type)}</Badge>
                  {s.is_entry && <Badge variant="secondary">entry</Badge>}
                  <span className="text-xs text-muted-foreground">on error: {s.on_error}</span>
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Remove step ${s.name}`}
                  onClick={() => delStep.mutateAsync(s.id)}
                  disabled={delStep.isPending}
                >
                  Delete
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-muted-foreground">
            {edgeRows.length} connection{edgeRows.length === 1 ? "" : "s"}
          </h3>
          <Button size="sm" variant="outline" disabled={stepRows.length < 2} onClick={() => setConnecting(true)}>
            Connect steps
          </Button>
        </div>
        <ul className="space-y-2">
          {edgeRows.map((e) => (
            <li key={e.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex items-center gap-2">
                <span className="font-medium">{stepName(e.source_step_id)}</span>
                <span aria-hidden className="text-muted-foreground">→</span>
                <span className="font-medium">{stepName(e.target_step_id)}</span>
                {e.condition_label && <Badge variant="outline">{e.condition_label}</Badge>}
              </span>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Remove connection ${stepName(e.source_step_id)} to ${stepName(e.target_step_id)}`}
                onClick={() => delEdge.mutateAsync(e.id)}
                disabled={delEdge.isPending}
              >
                Delete
              </Button>
            </li>
          ))}
          {edgeRows.length === 0 && (
            <li className={cn("rounded-md border border-dashed p-3 text-xs text-muted-foreground")}>
              {stepRows.length < 2 ? "Add two steps to connect them." : "No connections yet."}
            </li>
          )}
        </ul>
      </section>

      {addingStep && (
        <AddStepDialog definitionId={definitionId} hasEntry={stepRows.some((s) => s.is_entry)} open onOpenChange={setAddingStep} />
      )}
      {connecting && (
        <ConnectDialog definitionId={definitionId} steps={stepRows} open onOpenChange={setConnecting} />
      )}
    </div>
  );
}

function AddStepDialog({
  definitionId,
  hasEntry,
  open,
  onOpenChange,
}: {
  definitionId: string;
  hasEntry: boolean;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const create = useCreateStep(definitionId);
  const [name, setName] = useState("");
  const [stepType, setStepType] = useState("action_send_notification");
  const [onError, setOnError] = useState<StepErrorMode>("stop");
  const groups = Array.from(new Set(STEP_TYPE_OPTIONS.map((s) => s.group)));

  async function submit() {
    if (!name.trim()) return;
    try {
      await create.mutateAsync({
        name: name.trim(),
        step_type: stepType,
        on_error: onError,
        is_entry: !hasEntry, // first step becomes the entry node
      });
      toast.success("Step added");
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not add step");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add step</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="step-name">Name</Label>
            <Input id="step-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="step-type">Type</Label>
            <Select value={stepType} onValueChange={setStepType}>
              <SelectTrigger id="step-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {groups.map((g) => (
                  <SelectGroup key={g}>
                    <SelectLabel>{g}</SelectLabel>
                    {STEP_TYPE_OPTIONS.filter((s) => s.group === g).map((s) => (
                      <SelectItem key={s.value} value={s.value}>
                        {s.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="step-onerror">On error</Label>
            <Select value={onError} onValueChange={(v) => setOnError(v as StepErrorMode)}>
              <SelectTrigger id="step-onerror" className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ON_ERROR_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!name.trim() || create.isPending}>
            {create.isPending ? "Adding…" : "Add step"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ConnectDialog({
  definitionId,
  steps,
  open,
  onOpenChange,
}: {
  definitionId: string;
  steps: WorkflowStep[];
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const create = useCreateEdge(definitionId);
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [label, setLabel] = useState("");
  const valid = !!source && !!target && source !== target;

  async function submit() {
    if (!valid) return;
    try {
      await create.mutateAsync({ source_step_id: source, target_step_id: target, condition_label: label });
      toast.success("Connection added");
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not connect");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Connect steps</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="edge-source">From</Label>
            <Select value={source || undefined} onValueChange={setSource}>
              <SelectTrigger id="edge-source">
                <SelectValue placeholder="Source step" />
              </SelectTrigger>
              <SelectContent>
                {steps.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edge-target">To</Label>
            <Select value={target || undefined} onValueChange={setTarget}>
              <SelectTrigger id="edge-target">
                <SelectValue placeholder="Target step" />
              </SelectTrigger>
              <SelectContent>
                {steps.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="edge-label">Condition label (optional)</Label>
            <Input
              id="edge-label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="true / false / default"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid || create.isPending}>
            {create.isPending ? "Connecting…" : "Connect"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
