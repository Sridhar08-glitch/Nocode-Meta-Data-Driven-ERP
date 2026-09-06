"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "@/components/ui/toast";
import { authApi, type Session } from "@/lib/auth/api";

export default function SessionsPage() {
  const qc = useQueryClient();
  const sessions = useQuery({ queryKey: ["auth", "sessions"], queryFn: authApi.listSessions });

  const revoke = useMutation({
    mutationFn: (id: string) => authApi.revokeSession(id),
    onSuccess: () => {
      toast.success("Session revoked");
      qc.invalidateQueries({ queryKey: ["auth", "sessions"] });
    },
    onError: () => toast.error("Could not revoke session"),
  });

  const revokeOthers = useMutation({
    mutationFn: () => authApi.revokeAllSessions(),
    onSuccess: (r) => {
      toast.success(`Revoked ${r.revoked} session${r.revoked === 1 ? "" : "s"}`);
      qc.invalidateQueries({ queryKey: ["auth", "sessions"] });
    },
    onError: () => toast.error("Could not revoke sessions"),
  });

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Active sessions</h1>
          <p className="text-sm text-muted-foreground">
            Devices currently signed in to your account.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => revokeOthers.mutate()}
          disabled={revokeOthers.isPending || (sessions.data?.length ?? 0) === 0}
        >
          Revoke all
        </Button>
      </div>

      {sessions.isLoading && <Skeleton className="h-40 w-full" />}
      {sessions.isError && (
        <ErrorState
          title="Couldn't load sessions"
          action={{ label: "Retry", onClick: () => sessions.refetch() }}
        />
      )}
      {sessions.data?.length === 0 && <EmptyState title="No active sessions" />}

      {sessions.data && sessions.data.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Device</TableHead>
              <TableHead>IP</TableHead>
              <TableHead>Last seen</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sessions.data.map((s: Session) => (
              <TableRow key={s.id}>
                <TableCell className="max-w-xs truncate" title={s.user_agent}>
                  {s.user_agent || <Badge variant="outline">Unknown</Badge>}
                </TableCell>
                <TableCell>{s.ip_address ?? "—"}</TableCell>
                <TableCell>{new Date(s.last_seen).toLocaleString()}</TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => revoke.mutate(s.id)}
                    disabled={revoke.isPending}
                  >
                    Revoke
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
