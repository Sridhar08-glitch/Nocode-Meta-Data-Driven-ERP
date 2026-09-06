"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { WorkspaceMember } from "@/lib/tenant/admin-api";
import {
  useAddMember,
  useAssignRole,
  useMembers,
  useReactivateMember,
  useRemoveMember,
  useResetMemberPassword,
  useSuspendMember,
  useTransferOwnership,
} from "@/lib/tenant/admin-hooks";
import { useTenant } from "@/lib/tenant/context";

const ROLES = ["admin", "member", "viewer"] as const;

/** Workspace member roster + lifecycle (closes GAP-2..7). Owner/admin gated. */
export function MembersAdmin() {
  const { workspace } = useTenant();
  const myRole = workspace?.role ?? "viewer";
  const isAdmin = myRole === "owner" || myRole === "admin";
  const isOwner = myRole === "owner";

  const membersQuery = useMembers();
  const add = useAddMember();
  const assignRole = useAssignRole();
  const remove = useRemoveMember();
  const suspend = useSuspendMember();
  const reactivate = useReactivateMember();
  const resetPw = useResetMemberPassword();
  const transfer = useTransferOwnership();

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<(typeof ROLES)[number]>("member");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function flash(setter: (v: string | null) => void, value: string) {
    setter(value);
    window.setTimeout(() => setter(null), 4000);
  }
  function fail(err: unknown) {
    flash(setError, err instanceof Error ? err.message : "Something went wrong.");
  }

  async function onAdd(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await add.mutateAsync({ email: email.trim(), full_name: name.trim(), role });
      setEmail("");
      setName("");
      flash(setMsg, res.created_user
        ? "Account created — a set-password email was sent."
        : "Member added.");
    } catch (err) {
      fail(err);
    }
  }

  if (membersQuery.isError)
    return <ErrorState title="Couldn't load members" action={{ label: "Retry", onClick: () => membersQuery.refetch() }} />;
  const members = membersQuery.data ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Members</h1>
        <p className="text-sm text-muted-foreground">
          Invite teammates, assign roles, and manage access for {workspace?.name}.
        </p>
      </div>

      {isAdmin && (
        <form onSubmit={onAdd} className="flex flex-wrap items-end gap-3 rounded-lg border p-4">
          <div className="flex-1 min-w-[200px] space-y-1.5">
            <label className="text-xs font-medium" htmlFor="m-email">Email</label>
            <Input id="m-email" type="email" required value={email}
              onChange={(e) => setEmail(e.target.value)} placeholder="teammate@company.com" />
          </div>
          <div className="flex-1 min-w-[160px] space-y-1.5">
            <label className="text-xs font-medium" htmlFor="m-name">Full name (optional)</label>
            <Input id="m-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Doe" />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium">Role</label>
            <Select value={role} onValueChange={(v) => setRole(v as (typeof ROLES)[number])}>
              <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
              <SelectContent>
                {ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <Button type="submit" disabled={!email.trim() || add.isPending}>
            {add.isPending ? "Adding…" : "Add member"}
          </Button>
        </form>
      )}

      {msg && <p className="text-sm text-emerald-600">{msg}</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}

      {members.length === 0 ? (
        <EmptyState title="No members" description="Add your first teammate above." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Member</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {members.map((m: WorkspaceMember) => (
              <TableRow key={m.id}>
                <TableCell>
                  <div className="font-medium">{m.full_name || m.email}</div>
                  <div className="text-xs text-muted-foreground">{m.email}</div>
                </TableCell>
                <TableCell>
                  {m.is_owner ? (
                    <Badge>owner</Badge>
                  ) : isAdmin ? (
                    <Select
                      value={m.role}
                      onValueChange={(v) =>
                        assignRole.mutateAsync({ memberId: m.id, role: v }).catch(fail)}
                    >
                      <SelectTrigger className="w-28 h-8"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Badge variant="secondary">{m.role}</Badge>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant={m.status === "active" ? "secondary" : "outline"}>{m.status}</Badge>
                </TableCell>
                <TableCell className="text-right space-x-1">
                  {isAdmin && !m.is_owner && (
                    <>
                      {m.status === "active" ? (
                        <Button size="sm" variant="ghost"
                          onClick={() => suspend.mutateAsync(m.id).catch(fail)}>Suspend</Button>
                      ) : (
                        <Button size="sm" variant="ghost"
                          onClick={() => reactivate.mutateAsync(m.id).catch(fail)}>Reactivate</Button>
                      )}
                      <Button size="sm" variant="ghost"
                        onClick={() => resetPw.mutateAsync(m.id)
                          .then(() => flash(setMsg, "Password reset email sent.")).catch(fail)}>
                        Reset password
                      </Button>
                      {isOwner && m.status === "active" && (
                        <Button size="sm" variant="ghost"
                          onClick={() => {
                            if (window.confirm(`Transfer ownership to ${m.email}? You'll become an admin.`))
                              transfer.mutateAsync(m.id)
                                .then(() => flash(setMsg, "Ownership transferred.")).catch(fail);
                          }}>
                          Make owner
                        </Button>
                      )}
                      <Button size="sm" variant="ghost" className="text-destructive"
                        onClick={() => {
                          if (window.confirm(`Remove ${m.email} from the workspace?`))
                            remove.mutateAsync(m.id).catch(fail);
                        }}>
                        Remove
                      </Button>
                    </>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
