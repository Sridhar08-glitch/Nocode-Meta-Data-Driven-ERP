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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { isValidSlug, slugify } from "@/lib/metadata/slug";
import { useCreateRole, useRoles } from "@/lib/permissions/hooks";
import { cn } from "@/lib/utils";

import { FieldAccess } from "./field-access";
import { RoleGrants } from "./role-grants";

/** Visual RBAC + ABAC permission builder: roles list + per-role grants and field access. */
export function PermissionBuilder() {
  const roles = useRoles();
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  if (roles.isLoading) return <Skeleton className="h-64 w-full" />;
  if (roles.isError) return <ErrorState title="Couldn't load roles" />;
  const rows = roles.data ?? [];
  const activeId = selected ?? rows[0]?.id ?? null;
  const active = rows.find((r) => r.id === activeId) ?? null;

  return (
    <div className="grid gap-6 md:grid-cols-[220px_1fr]">
      <aside className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-muted-foreground">Roles</h2>
          <Button size="sm" variant="outline" onClick={() => setCreating(true)}>
            New
          </Button>
        </div>
        {rows.length === 0 ? (
          <EmptyState title="No roles" description="Create a role to assign permissions." />
        ) : (
          <ul className="space-y-1">
            {rows.map((r) => (
              <li key={r.id}>
                <button
                  className={cn(
                    "flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted",
                    r.id === activeId && "bg-muted font-medium",
                  )}
                  onClick={() => setSelected(r.id)}
                >
                  <span>{r.name}</span>
                  {r.is_system && <Badge variant="outline">system</Badge>}
                </button>
              </li>
            ))}
          </ul>
        )}
        {creating && <CreateRoleDialog open={creating} onOpenChange={setCreating} onCreated={setSelected} />}
      </aside>

      <div>
        {active ? (
          <Tabs defaultValue="grants" key={active.id}>
            <div className="mb-3">
              <h2 className="text-lg font-semibold">{active.name}</h2>
              <p className="text-sm text-muted-foreground">{active.description || "No description."}</p>
            </div>
            <TabsList>
              <TabsTrigger value="grants">Permissions</TabsTrigger>
              <TabsTrigger value="fields">Field access</TabsTrigger>
            </TabsList>
            <TabsContent value="grants" className="pt-4">
              <RoleGrants roleId={active.id} />
            </TabsContent>
            <TabsContent value="fields" className="pt-4">
              <FieldAccess roleId={active.id} />
            </TabsContent>
          </Tabs>
        ) : (
          <EmptyState title="Select a role" description="Pick a role to edit its permissions." />
        )}
      </div>
    </div>
  );
}

function CreateRoleDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onCreated: (id: string) => void;
}) {
  const create = useCreateRole();
  const [name, setName] = useState("");
  const slug = slugify(name);
  const valid = !!name.trim() && isValidSlug(slug);

  async function submit() {
    if (!valid) return;
    try {
      const role = await create.mutateAsync({ name: name.trim(), slug });
      toast.success(`Created “${role.name}”`);
      onCreated(role.id);
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create role");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New role</DialogTitle>
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="role-name">Name</Label>
          <Input id="role-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
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
