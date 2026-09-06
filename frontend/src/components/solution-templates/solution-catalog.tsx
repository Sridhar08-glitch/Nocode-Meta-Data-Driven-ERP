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
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type {
  InstalledSolution,
  PreviewSummary,
  SolutionTemplate,
} from "@/lib/solution-templates/api";
import {
  useInstallTemplate,
  useInstalledSolutions,
  useTemplatePreview,
  useTemplates,
  useUninstallSolution,
} from "@/lib/solution-templates/hooks";
import { useTenant } from "@/lib/tenant/context";

const SUMMARY_LABELS: { key: keyof PreviewSummary; label: string }[] = [
  { key: "entities", label: "Entities" },
  { key: "forms", label: "Forms" },
  { key: "views", label: "Views" },
  { key: "workflows", label: "Workflows" },
  { key: "rules", label: "Rules" },
  { key: "reports", label: "Reports" },
  { key: "roles", label: "Roles" },
  { key: "dashboards", label: "Dashboards" },
  { key: "applications", label: "Apps" },
];

/** Whether the caller may install/uninstall (the API gates writes regardless). */
function useCanManage(): boolean {
  const { workspace } = useTenant();
  const role = workspace?.role;
  return role === "owner" || role === "admin";
}

/** Solution Template Framework (Phase P2.4A): browse + install curated solutions, manage installed. */
export function SolutionCatalog() {
  const canManage = useCanManage();
  return (
    <Tabs defaultValue="browse" className="space-y-4">
      <TabsList>
        <TabsTrigger value="browse">Browse</TabsTrigger>
        <TabsTrigger value="installed">Installed</TabsTrigger>
      </TabsList>
      <TabsContent value="browse">
        <Browse canManage={canManage} />
      </TabsContent>
      <TabsContent value="installed">
        <InstalledSolutions canManage={canManage} />
      </TabsContent>
    </Tabs>
  );
}

export function Browse({ canManage }: { canManage: boolean }) {
  const [search, setSearch] = useState("");
  const templates = useTemplates(search.trim() ? { search: search.trim() } : {});
  const [previewing, setPreviewing] = useState<SolutionTemplate | null>(null);

  const rows = templates.data?.results ?? [];

  return (
    <div className="space-y-4">
      <Input
        aria-label="Search solutions"
        placeholder="Search solutions…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
      />

      {templates.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : templates.isError ? (
        <ErrorState title="Couldn't load solutions" />
      ) : rows.length === 0 ? (
        <EmptyState title="No solutions found" description="No published solution templates match your search." />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                onClick={() => setPreviewing(t)}
                aria-label={`Preview ${t.name}`}
                className="flex h-full w-full flex-col items-start gap-1 rounded-lg border p-4 text-left transition-colors hover:bg-accent"
              >
                <div className="flex w-full items-center justify-between gap-2">
                  <span className="flex items-center gap-2 font-medium">
                    {t.icon && <span aria-hidden>{t.icon}</span>}
                    {t.name}
                  </span>
                  {t.category && <Badge variant="outline">{t.category}</Badge>}
                </div>
                {t.description && <span className="line-clamp-2 text-xs text-muted-foreground">{t.description}</span>}
                <span className="mt-1 flex flex-wrap gap-1 text-xs text-muted-foreground">
                  <Badge variant="secondary">{t.summary.entities} entities</Badge>
                  <Badge variant="secondary">{t.summary.workflows} workflows</Badge>
                  <Badge variant="secondary">{t.summary.applications} apps</Badge>
                </span>
                <span className="mt-auto pt-1 text-xs text-muted-foreground">
                  v{t.version} · {t.install_count} install(s)
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {previewing && (
        <PreviewDialog open template={previewing} canManage={canManage} onClose={() => setPreviewing(null)} />
      )}
    </div>
  );
}

function PreviewDialog({
  open,
  template,
  canManage,
  onClose,
}: {
  open: boolean;
  template: SolutionTemplate;
  canManage: boolean;
  onClose: () => void;
}) {
  const preview = useTemplatePreview(template.id);
  const install = useInstallTemplate();
  const [consented, setConsented] = useState(false);

  const data = preview.data;

  async function doInstall() {
    try {
      const res = await install.mutateAsync(template.id);
      toast.success(`Installed “${res.solution_name}” (${res.created_entity_ids.length} entities)`);
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not install solution");
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{template.name}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {template.description && <p className="text-sm text-muted-foreground">{template.description}</p>}

          {preview.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : preview.isError ? (
            <ErrorState title="Couldn't load preview" />
          ) : data ? (
            <>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
                {SUMMARY_LABELS.map(({ key, label }) => (
                  <div key={key} aria-label={label} className="rounded-md border p-2 text-center">
                    <div className="text-lg font-semibold tabular-nums">{data.summary[key]}</div>
                    <div className="text-xs text-muted-foreground">{label}</div>
                  </div>
                ))}
              </div>

              {!data.valid && (
                <div role="alert" className="space-y-1 rounded-md border border-destructive/40 p-2 text-xs text-destructive">
                  <p className="font-medium">This solution has manifest errors and can&apos;t be installed:</p>
                  {data.errors.map((e) => (
                    <p key={e}>{e}</p>
                  ))}
                </div>
              )}

              {canManage ? (
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={consented}
                    onChange={(e) => setConsented(e.target.checked)}
                    aria-label="Consent to install"
                  />
                  I understand this provisions entities, forms, views, workflows, and more into my workspace.
                </label>
              ) : (
                <p className="text-xs text-muted-foreground">Only workspace owners and admins can install solutions.</p>
              )}
            </>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          {canManage && (
            <Button onClick={doInstall} disabled={!data?.valid || !consented || install.isPending}>
              {install.isPending ? "Installing…" : "Install solution"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function InstalledSolutions({ canManage }: { canManage: boolean }) {
  const installed = useInstalledSolutions();
  const uninstall = useUninstallSolution();
  const [confirm, setConfirm] = useState<InstalledSolution | null>(null);

  const rows = installed.data?.results ?? [];

  async function doUninstall(hard: boolean) {
    if (!confirm) return;
    try {
      await uninstall.mutateAsync({ id: confirm.id, hard });
      toast.success(hard ? "Solution hard-uninstalled" : "Solution uninstalled");
      setConfirm(null);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Uninstall failed");
    }
  }

  if (installed.isLoading) return <Skeleton className="h-40 w-full" />;
  if (installed.isError) return <ErrorState title="Couldn't load installed solutions" />;
  if (rows.length === 0) return <EmptyState title="No solutions installed" description="Install a solution from Browse." />;

  return (
    <div className="space-y-2">
      <ul className="space-y-2">
        {rows.map((s) => (
          <li key={s.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
            <span className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{s.solution_name}</span>
              <Badge variant="outline">v{s.installed_version}</Badge>
              <Badge variant={s.status === "active" ? "default" : "secondary"}>{s.status}</Badge>
              <span className="text-xs text-muted-foreground">
                {s.created_entity_ids.length} entities · {s.created_application_ids.length} apps
              </span>
            </span>
            {canManage && (
              <span className="flex shrink-0 items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Uninstall ${s.solution_name}`}
                  onClick={() => setConfirm(s)}
                  disabled={s.status !== "active"}
                >
                  Uninstall
                </Button>
              </span>
            )}
          </li>
        ))}
      </ul>

      <Dialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Uninstall {confirm?.solution_name}?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Soft uninstall deactivates the solution&apos;s workflows &amp; rules but keeps entities and
            records. Hard uninstall also soft-deletes the solution&apos;s entity definitions (records remain).
          </p>
          <DialogFooter className="gap-2">
            <Button variant="ghost" onClick={() => setConfirm(null)}>
              Cancel
            </Button>
            <Button variant="outline" onClick={() => doUninstall(false)} disabled={uninstall.isPending}>
              Soft uninstall
            </Button>
            <Button onClick={() => doUninstall(true)} disabled={uninstall.isPending}>
              Hard uninstall
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
