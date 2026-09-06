"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { EntityCreateDialog } from "@/components/builder/entity-create-dialog";
import { PublishBar } from "@/components/builder/publish-bar";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { useEntities } from "@/lib/metadata/hooks";

const STUDIO_LINKS = [
  { href: "/studio/applications", label: "Applications" },
  { href: "/studio/home-layouts", label: "Home layouts" },
  { href: "/studio/navigation", label: "Navigation" },
];

export default function StudioPage() {
  const router = useRouter();
  const entities = useEntities();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Studio</h1>
          <p className="text-sm text-muted-foreground">Build entities, fields, relationships, and forms.</p>
        </div>
        <div className="flex items-center gap-3">
          <PublishBar />
          <EntityCreateDialog onCreated={(slug) => router.push(`/studio/${slug}`)} />
        </div>
      </div>

      <nav className="flex flex-wrap gap-2" aria-label="Studio sections">
        {STUDIO_LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className="rounded-md border px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            {l.label}
          </Link>
        ))}
      </nav>

      {entities.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : entities.isError ? (
        <ErrorState title="Couldn't load entities" />
      ) : (entities.data ?? []).length === 0 ? (
        <EmptyState
          title="No entities yet"
          description="Create your first entity to start building."
        />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(entities.data ?? []).map((e) => (
            <li key={e.id}>
              <button
                type="button"
                onClick={() => router.push(`/studio/${e.slug}`)}
                className="flex w-full flex-col items-start gap-1 rounded-lg border p-4 text-left transition-colors hover:bg-accent"
              >
                <div className="flex w-full items-center justify-between">
                  <span className="font-medium">{e.name}</span>
                  {!e.is_active && <Badge variant="outline">archived</Badge>}
                </div>
                <span className="font-mono text-xs text-muted-foreground">{e.slug}</span>
                <span className="text-xs text-muted-foreground">
                  {e.fields.length} fields · v{e.current_schema_version}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
