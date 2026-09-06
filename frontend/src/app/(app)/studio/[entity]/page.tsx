"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { EntitySettings } from "@/components/builder/entity-settings";
import { FieldsPanel } from "@/components/builder/fields-panel";
import { FormsPanel } from "@/components/builder/forms-panel";
import { PublishBar } from "@/components/builder/publish-bar";
import { RelationshipsPanel } from "@/components/builder/relationships-panel";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ErrorState } from "@/components/ui/states";
import { useEntityMeta } from "@/lib/metadata/hooks";

export default function EntityBuilderPage({ params }: { params: { entity: string } }) {
  const slug = params.entity;
  const router = useRouter();
  const { entity, isLoading, isError } = useEntityMeta(slug);

  if (isLoading) return <Skeleton className="h-96 w-full" />;
  if (isError || !entity) return <ErrorState title="Entity not found" />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => router.push("/studio")}>
            ← Studio
          </Button>
          <div>
            <h1 className="text-xl font-semibold">{entity.name}</h1>
            <p className="font-mono text-xs text-muted-foreground">{entity.slug}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" asChild>
            <Link href={`/e/${slug}`}>View records →</Link>
          </Button>
          <PublishBar />
        </div>
      </div>

      <Tabs defaultValue="fields">
        <TabsList>
          <TabsTrigger value="fields">Fields</TabsTrigger>
          <TabsTrigger value="relationships">Relationships</TabsTrigger>
          <TabsTrigger value="forms">Forms</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>
        <TabsContent value="fields" className="pt-4">
          <FieldsPanel entity={slug} />
        </TabsContent>
        <TabsContent value="relationships" className="pt-4">
          <RelationshipsPanel entityId={entity.id} />
        </TabsContent>
        <TabsContent value="forms" className="pt-4">
          <FormsPanel entity={slug} />
        </TabsContent>
        <TabsContent value="settings" className="pt-4">
          <EntitySettings entity={entity} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
