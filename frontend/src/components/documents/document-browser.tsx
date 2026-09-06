"use client";

import { useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { type DocumentItem, documentsApi, resolveDownloadUrl } from "@/lib/documents/api";
import {
  useCreateFolder,
  useDeleteDocument,
  useDeleteFolder,
  useDocuments,
  useDocumentVersions,
  useFolders,
  useUploadDocument,
  useUploadVersion,
} from "@/lib/documents/hooks";

function fmtBytes(n: number): string {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB"];
  const i = Math.min(u.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
  return `${(n / 1024 ** i).toFixed(1)} ${u[i]}`;
}

/** Document management (Phase P1.2): folder navigation + upload + versions + download + delete. */
export function DocumentBrowser() {
  const folders = useFolders();
  const createFolder = useCreateFolder();
  const delFolder = useDeleteFolder();
  const upload = useUploadDocument();
  const delDoc = useDeleteDocument();
  const [folderId, setFolderId] = useState<string | null>(null);
  const [versionsFor, setVersionsFor] = useState<DocumentItem | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const docs = useDocuments({ folder_id: folderId });
  const folderRows = folders.data?.results ?? [];

  async function newFolder() {
    const name = window.prompt("Folder name");
    if (!name?.trim()) return;
    try {
      await createFolder.mutateAsync({ name: name.trim(), parent_id: folderId });
      toast.success("Folder created");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create folder");
    }
  }
  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    if (folderId) form.append("folder_id", folderId);
    try {
      await upload.mutateAsync(form);
      toast.success("Uploaded");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Upload failed");
    }
  }
  async function download(doc: DocumentItem) {
    try {
      const { url } = await documentsApi.downloadUrl(doc.id);
      window.open(resolveDownloadUrl(url), "_blank", "noopener");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not get download link");
    }
  }
  async function removeDoc(doc: DocumentItem) {
    try {
      await delDoc.mutateAsync(doc.id);
      toast.success("Moved to recycle bin");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not delete");
    }
  }
  async function removeFolder(id: string) {
    try {
      await delFolder.mutateAsync(id);
      if (folderId === id) setFolderId(null);
      toast.success("Folder removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove folder");
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
      {/* Folder sidebar */}
      <aside className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-muted-foreground">Folders</h2>
          <Button variant="outline" size="sm" className="h-7" onClick={newFolder}>
            New
          </Button>
        </div>
        <button
          type="button"
          onClick={() => setFolderId(null)}
          className={`w-full rounded-md px-3 py-2 text-left text-sm ${folderId === null ? "bg-primary/10 font-medium text-primary" : "hover:bg-muted"}`}
        >
          All documents
        </button>
        {folders.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <ul className="space-y-0.5">
            {[...folderRows]
              .sort((a, b) => a.path.localeCompare(b.path))
              .map((f) => {
                const depth = Math.max(0, (f.path.match(/\//g)?.length ?? 1) - 1);
                return (
                  <li key={f.id} className="group flex items-center">
                    <button
                      type="button"
                      onClick={() => setFolderId(f.id)}
                      style={{ paddingLeft: `${0.75 + depth * 0.75}rem` }}
                      className={`flex-1 truncate rounded-md py-2 pr-2 text-left text-sm ${folderId === f.id ? "bg-primary/10 font-medium text-primary" : "hover:bg-muted"}`}
                    >
                      {f.name}
                    </button>
                    <Button variant="ghost" size="sm" aria-label={`Remove folder ${f.name}`} className="h-7 opacity-0 group-hover:opacity-100" onClick={() => removeFolder(f.id)}>
                      ✕
                    </Button>
                  </li>
                );
              })}
          </ul>
        )}
      </aside>

      {/* Document list */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-muted-foreground">Documents</h2>
          <div>
            <input ref={fileInput} type="file" className="hidden" aria-label="Upload file" onChange={onPickFile} />
            <Button size="sm" onClick={() => fileInput.current?.click()} disabled={upload.isPending}>
              {upload.isPending ? "Uploading…" : "Upload"}
            </Button>
          </div>
        </div>

        {docs.isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : docs.isError ? (
          <ErrorState title="Couldn't load documents" />
        ) : (docs.data?.results ?? []).length === 0 ? (
          <EmptyState title="No documents" description="Upload a file to this folder." action={{ label: "Upload", onClick: () => fileInput.current?.click() }} />
        ) : (
          <ul className="space-y-2">
            {(docs.data?.results ?? []).map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
                <span className="flex min-w-0 flex-wrap items-center gap-2">
                  <span className="truncate font-medium">{d.name}</span>
                  {d.extension && <Badge variant="outline">{d.extension}</Badge>}
                  <span className="text-xs text-muted-foreground">{fmtBytes(d.size_bytes)} · v{d.current_version}</span>
                  {d.av_clean === false && <Badge variant="destructive">quarantined</Badge>}
                </span>
                <span className="flex shrink-0 items-center gap-1">
                  <Button variant="ghost" size="sm" aria-label={`Download ${d.name}`} onClick={() => download(d)} disabled={d.av_clean === false}>
                    Download
                  </Button>
                  <Button variant="ghost" size="sm" aria-label={`Versions of ${d.name}`} onClick={() => setVersionsFor(d)}>
                    Versions
                  </Button>
                  <Button variant="ghost" size="sm" aria-label={`Delete ${d.name}`} onClick={() => removeDoc(d)} disabled={delDoc.isPending}>
                    Delete
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {versionsFor && <VersionsDialog doc={versionsFor} onClose={() => setVersionsFor(null)} />}
    </div>
  );
}

function VersionsDialog({ doc, onClose }: { doc: DocumentItem; onClose: () => void }) {
  const versions = useDocumentVersions(doc.id);
  const uploadVersion = useUploadVersion();
  const fileInput = useRef<HTMLInputElement>(null);
  const rows = versions.data?.results ?? [];

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    try {
      await uploadVersion.mutateAsync({ id: doc.id, form });
      toast.success("New version uploaded");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not upload version");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Versions — {doc.name}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <input ref={fileInput} type="file" className="hidden" aria-label="Upload new version" onChange={onPick} />
            <Button variant="outline" size="sm" onClick={() => fileInput.current?.click()} disabled={uploadVersion.isPending}>
              {uploadVersion.isPending ? "Uploading…" : "Upload new version"}
            </Button>
          </div>
          {versions.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">No version history.</p>
          ) : (
            <ul className="max-h-72 space-y-1.5 overflow-y-auto">
              {rows.map((v) => (
                <li key={v.id} className="flex items-center justify-between gap-2 rounded-md border p-2 text-xs">
                  <span className="flex items-center gap-2">
                    <Badge variant="outline">v{v.version_number}</Badge>
                    {v.comment && <span className="text-muted-foreground">{v.comment}</span>}
                  </span>
                  <span className="text-muted-foreground">{fmtBytes(v.size_bytes)} · {v.created_at ? new Date(v.created_at).toLocaleDateString() : ""}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
