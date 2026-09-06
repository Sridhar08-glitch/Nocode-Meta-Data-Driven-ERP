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
import type { InstalledPlugin } from "@/lib/marketplace/api";
import {
  useInstallPlugin,
  useInstalledPlugins,
  usePluginDetail,
  usePlugins,
  useRollbackPlugin,
  useUninstallPlugin,
  useUpgradePlugin,
} from "@/lib/marketplace/hooks";

/** A plugin opened in the install/upgrade dialog. `installedId` set ⇒ upgrade mode. */
interface DialogTarget {
  pluginId: string;
  name: string;
  description?: string;
  installedId?: string;
}

/** Marketplace store (Phase F3.4): browse + install plugins, manage installed (upgrade/rollback/uninstall). */
export function MarketplaceStore() {
  const [target, setTarget] = useState<DialogTarget | null>(null);
  return (
    <Tabs defaultValue="browse" className="space-y-4">
      <TabsList>
        <TabsTrigger value="browse">Browse</TabsTrigger>
        <TabsTrigger value="installed">Installed</TabsTrigger>
      </TabsList>
      <TabsContent value="browse">
        <Browse onOpen={setTarget} />
      </TabsContent>
      <TabsContent value="installed">
        <MarketplaceInstalled onUpgrade={setTarget} />
      </TabsContent>
      {target && <PluginDialog target={target} onClose={() => setTarget(null)} />}
    </Tabs>
  );
}

function Browse({ onOpen }: { onOpen: (t: DialogTarget) => void }) {
  const [search, setSearch] = useState("");
  const plugins = usePlugins(search.trim() ? { search: search.trim() } : {});
  const rows = plugins.data?.results ?? [];

  return (
    <div className="space-y-4">
      <Input aria-label="Search plugins" placeholder="Search plugins…" value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-sm" />
      {plugins.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : plugins.isError ? (
        <ErrorState title="Couldn't load the marketplace" />
      ) : rows.length === 0 ? (
        <EmptyState title="No plugins found" description="No published plugins match your search." />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((p) => (
            <li key={p.id}>
              <button type="button" aria-label={`Open ${p.name}`} onClick={() => onOpen({ pluginId: p.id, name: p.name, description: p.description })} className="flex h-full w-full flex-col items-start gap-1 rounded-lg border p-4 text-left transition-colors hover:bg-accent">
                <div className="flex w-full items-center justify-between gap-2">
                  <span className="font-medium">{p.name}</span>
                  {p.is_official && <Badge>official</Badge>}
                </div>
                {p.tagline && <span className="line-clamp-2 text-xs text-muted-foreground">{p.tagline}</span>}
                <span className="mt-auto text-xs text-muted-foreground">v{p.latest_version} · {p.install_count} install(s)</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function MarketplaceInstalled({ onUpgrade }: { onUpgrade: (t: DialogTarget) => void }) {
  const installed = useInstalledPlugins();
  const uninstall = useUninstallPlugin();
  const rollback = useRollbackPlugin();
  const [confirm, setConfirm] = useState<InstalledPlugin | null>(null);

  const rows = installed.data?.results ?? [];

  async function doRollback(id: string) {
    try {
      await rollback.mutateAsync(id);
      toast.success("Rolled back");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Rollback failed");
    }
  }
  async function doUninstall(hard: boolean) {
    if (!confirm) return;
    try {
      await uninstall.mutateAsync({ id: confirm.id, hard });
      toast.success(hard ? "Plugin hard-uninstalled" : "Plugin uninstalled");
      setConfirm(null);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Uninstall failed");
    }
  }

  if (installed.isLoading) return <Skeleton className="h-40 w-full" />;
  if (installed.isError) return <ErrorState title="Couldn't load installed plugins" />;
  if (rows.length === 0) return <EmptyState title="No plugins installed" description="Install a plugin from Browse." />;

  return (
    <div className="space-y-2">
      <ul className="space-y-2">
        {rows.map((ip) => (
          <li key={ip.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
            <span className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{ip.plugin_slug}</span>
              <Badge variant="outline">v{ip.installed_version}</Badge>
              <Badge variant={ip.status === "active" ? "default" : "secondary"}>{ip.status}</Badge>
              <span className="text-xs text-muted-foreground">
                {ip.created_entity_ids.length} entities · {ip.created_workflow_ids.length} workflows
              </span>
            </span>
            <span className="flex shrink-0 items-center gap-1">
              <Button variant="ghost" size="sm" aria-label={`Upgrade ${ip.plugin_slug}`} onClick={() => onUpgrade({ pluginId: ip.plugin_id, name: ip.plugin_slug, installedId: ip.id })}>
                Upgrade
              </Button>
              <Button variant="ghost" size="sm" aria-label={`Rollback ${ip.plugin_slug}`} onClick={() => doRollback(ip.id)} disabled={rollback.isPending}>
                Rollback
              </Button>
              <Button variant="ghost" size="sm" aria-label={`Uninstall ${ip.plugin_slug}`} onClick={() => setConfirm(ip)}>
                Uninstall
              </Button>
            </span>
          </li>
        ))}
      </ul>

      <Dialog open={!!confirm} onOpenChange={(o) => !o && setConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Uninstall {confirm?.plugin_slug}?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Soft uninstall deactivates workflows/rules but keeps entities &amp; records. Hard
            uninstall also soft-deletes the plugin&apos;s entity definitions (records remain).
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

function PluginDialog({ target, onClose }: { target: DialogTarget; onClose: () => void }) {
  const detail = usePluginDetail(target.pluginId);
  const install = useInstallPlugin();
  const upgrade = useUpgradePlugin();
  const [versionId, setVersionId] = useState("");

  const versions = detail.data?.versions ?? [];
  const chosen = versionId || versions[0]?.id || "";
  const isUpgrade = !!target.installedId;

  async function go() {
    if (!chosen) return;
    try {
      if (isUpgrade) {
        await upgrade.mutateAsync({ id: target.installedId!, versionId: chosen });
        toast.success("Plugin upgraded");
      } else {
        await install.mutateAsync({ pluginId: target.pluginId, versionId: chosen });
        toast.success(`Installed ${target.name}`);
      }
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Operation failed");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isUpgrade ? `Upgrade ${target.name}` : target.name}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          {target.description && <p className="text-sm text-muted-foreground">{target.description}</p>}
          {detail.isLoading ? (
            <Skeleton className="h-20 w-full" />
          ) : versions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No published versions.</p>
          ) : (
            <ul className="space-y-1.5">
              {versions.map((v) => (
                <li key={v.id}>
                  <label className="flex items-center gap-2 rounded-md border p-2 text-sm">
                    <input type="radio" name="plugin-version" aria-label={`Version ${v.version}`} checked={chosen === v.id} onChange={() => setVersionId(v.id)} />
                    <span className="font-medium">v{v.version}</span>
                    {v.changelog && <span className="truncate text-xs text-muted-foreground">{v.changelog}</span>}
                  </label>
                </li>
              ))}
            </ul>
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={go} disabled={!chosen || install.isPending || upgrade.isPending}>
            {isUpgrade ? "Upgrade" : "Install"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
