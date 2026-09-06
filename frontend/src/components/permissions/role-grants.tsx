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
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import {
  ACTION_OPTIONS,
  type AbacCondition,
  type PermissionAction,
  RESOURCE_TYPE_OPTIONS,
  type ResourceType,
} from "@/lib/permissions/api";
import { useCreatePermission, useDeletePermission, usePermissions } from "@/lib/permissions/hooks";

import { AbacConditions } from "./abac-conditions";

/** RBAC + ABAC grants for a single role. */
export function RoleGrants({ roleId }: { roleId: string }) {
  const grants = usePermissions(roleId);
  const del = useDeletePermission();
  const [adding, setAdding] = useState(false);

  if (grants.isLoading) return <Skeleton className="h-40 w-full" />;
  if (grants.isError) return <ErrorState title="Couldn't load permissions" />;
  const rows = grants.data ?? [];

  async function remove(id: string) {
    try {
      await del.mutateAsync(id);
      toast.success("Permission removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove permission");
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">{rows.length} grants</h3>
        <Button size="sm" onClick={() => setAdding(true)}>
          Add permission
        </Button>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No permissions"
          description="Grant this role access to resources."
          action={{ label: "Add permission", onClick: () => setAdding(true) }}
        />
      ) : (
        <ul className="space-y-2">
          {rows.map((g) => (
            <li
              key={g.id}
              className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm"
            >
              <div className="flex flex-wrap items-center gap-2">
                {g.is_deny ? <Badge variant="destructive">deny</Badge> : <Badge>allow</Badge>}
                <span className="font-medium">{g.action}</span>
                <span className="text-muted-foreground">on</span>
                <span className="font-medium">{g.resource_type}</span>
                {g.resource_id && (
                  <span className="font-mono text-xs text-muted-foreground">{g.resource_id}</span>
                )}
                {g.conditions.length > 0 && (
                  <Badge variant="outline">{g.conditions.length} condition(s)</Badge>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Remove ${g.action} on ${g.resource_type}`}
                onClick={() => remove(g.id)}
                disabled={del.isPending}
              >
                Delete
              </Button>
            </li>
          ))}
        </ul>
      )}

      {adding && <AddGrantDialog roleId={roleId} open={adding} onOpenChange={setAdding} />}
    </div>
  );
}

function AddGrantDialog({
  roleId,
  open,
  onOpenChange,
}: {
  roleId: string;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const create = useCreatePermission();
  const [resourceType, setResourceType] = useState<ResourceType>("entity");
  const [action, setAction] = useState<PermissionAction>("read");
  const [isDeny, setIsDeny] = useState(false);
  const [conditions, setConditions] = useState<AbacCondition[]>([]);

  async function submit() {
    try {
      await create.mutateAsync({
        role: roleId,
        resource_type: resourceType,
        action,
        is_deny: isDeny,
        conditions,
      });
      toast.success("Permission added");
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not add permission");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add permission</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="grant-resource">Resource</Label>
              <Select value={resourceType} onValueChange={(v) => setResourceType(v as ResourceType)}>
                <SelectTrigger id="grant-resource" className="w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {RESOURCE_TYPE_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="grant-action">Action</Label>
              <Select value={action} onValueChange={(v) => setAction(v as PermissionAction)}>
                <SelectTrigger id="grant-action" className="w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ACTION_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={isDeny} onCheckedChange={(v) => setIsDeny(!!v)} /> Explicit deny
            (overrides allow)
          </label>
          <div className="space-y-1.5">
            <Label>ABAC conditions</Label>
            <AbacConditions value={conditions} onChange={setConditions} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={create.isPending}>
            {create.isPending ? "Adding…" : "Add"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
