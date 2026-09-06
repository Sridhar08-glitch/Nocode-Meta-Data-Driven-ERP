"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState, PermissionDeniedState } from "@/components/ui/states";
import { Stepper } from "@/components/ui/stepper";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type {
  LibraryObject,
  PreviewSummary,
  WizardConfig,
  WizardLibrary,
  WizardOptions,
  WizardPreview,
  WizardRecommends,
  WizardSelection,
} from "@/lib/solution-templates/api";
import {
  useCreateSolution,
  usePreviewSolution,
  useResolveDependencies,
  useWizardOptions,
} from "@/lib/solution-templates/hooks";
import { useTenant } from "@/lib/tenant/context";

/* ------------------------------------------------------------------ *
 * Create Solution Wizard (Phase P2.4B) — guided 6-step composer that
 * assembles a WizardSelection from the library + recommend presets,
 * previews the resolved manifest, then provisions the solution.
 * ------------------------------------------------------------------ */

const STEPS = [
  { id: "type", label: "Type" },
  { id: "industry", label: "Industry" },
  { id: "blocks", label: "Building blocks" },
  { id: "configure", label: "Configure" },
  { id: "preview", label: "Preview" },
  { id: "create", label: "Create" },
];

/** Fixed report keys (not part of the object library — backend-defined). */
const REPORT_KEYS = ["summary", "detail", "trend", "aging", "kpi"] as const;
const REPORT_LABELS: Record<string, string> = {
  summary: "Summary",
  detail: "Detail",
  trend: "Trend",
  aging: "Aging",
  kpi: "KPI",
};

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

function useCanManage(): boolean {
  const { workspace } = useTenant();
  const role = workspace?.role;
  return role === "owner" || role === "admin";
}

/** Mutable selection state held across steps (config is owned by RHF on the Configure step). */
interface Draft {
  solution_type: string;
  industry: string | null;
  business_objects: string[];
  workflows: string[];
  roles: string[];
  dashboards: string[];
  reports: string[];
  config: WizardConfig;
}

const EMPTY_DRAFT: Draft = {
  solution_type: "",
  industry: null,
  business_objects: [],
  workflows: [],
  roles: [],
  dashboards: [],
  reports: [],
  config: { solution_name: "", application_name: "", description: "", icon: "", color: "#2563eb" },
};

/** Page entry point: gates non-admins, loads options, then renders the stepper. */
export function CreateSolutionWizard() {
  const canManage = useCanManage();
  const options = useWizardOptions();

  if (!canManage) {
    return (
      <PermissionDeniedState
        title="Only owners and admins can create solutions"
        description="Ask a workspace owner or admin to provision a solution for you."
      />
    );
  }
  if (options.isLoading) return <Skeleton className="h-96 w-full" />;
  if (options.isError || !options.data) {
    return <ErrorState title="Couldn't load the solution library" />;
  }
  return <WizardFlow options={options.data} />;
}

export function WizardFlow({ options }: { options: WizardOptions }) {
  const router = useRouter();
  const [stepIndex, setStepIndex] = useState(0);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [resolvedObjects, setResolvedObjects] = useState<string[]>([]);

  const resolve = useResolveDependencies();
  const preview = usePreviewSolution();
  const previewData = preview.data ?? null;
  const create = useCreateSolution();

  /** Merge a recommend preset into the current selections (recommend-only; user may change). */
  const applyRecommends = useCallback((rec: WizardRecommends) => {
    setDraft((d) => ({
      ...d,
      business_objects: rec.business_objects ?? [],
      workflows: rec.workflows ?? [],
      roles: rec.roles ?? [],
      dashboards: rec.dashboards ?? [],
      reports: rec.reports ?? [],
    }));
  }, []);

  function chooseType(key: string) {
    const t = options.solution_types.find((x) => x.key === key);
    setDraft((d) => ({ ...d, solution_type: key }));
    if (t) applyRecommends(t.recommends);
  }

  function chooseIndustry(key: string | null) {
    setDraft((d) => ({ ...d, industry: key }));
    if (key) {
      const ind = options.industries.find((x) => x.key === key);
      if (ind) applyRecommends(ind.recommends);
    }
  }

  // Live auto-included dependency resolution as the selected business objects change.
  const boKey = draft.business_objects.join(",");
  useEffect(() => {
    if (draft.business_objects.length === 0) {
      setResolvedObjects([]);
      return;
    }
    let cancelled = false;
    resolve
      .mutateAsync(draft.business_objects)
      .then((r) => {
        if (!cancelled) setResolvedObjects(r.resolved_objects);
      })
      .catch(() => {
        if (!cancelled) setResolvedObjects(draft.business_objects);
      });
    return () => {
      cancelled = true;
    };
    // resolve.mutateAsync is stable for our purposes; key on the joined slug list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [boKey]);

  const selection = useMemo<WizardSelection>(
    () => ({
      solution_type: draft.solution_type,
      industry: draft.industry,
      business_objects: draft.business_objects,
      workflows: draft.workflows,
      roles: draft.roles,
      dashboards: draft.dashboards,
      reports: draft.reports,
      config: draft.config,
    }),
    [draft],
  );

  function setConfig(config: WizardConfig) {
    setDraft((d) => ({ ...d, config }));
    setStepIndex(4);
    // Kick off the preview as soon as configuration is committed.
    void runPreview({ ...selection, config });
  }

  async function runPreview(sel: WizardSelection) {
    try {
      await preview.mutateAsync(sel);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Preview failed");
    }
  }

  async function doCreate() {
    try {
      const res = await create.mutateAsync(selection);
      toast.success(`Created “${res.solution_name}” (${res.created_entity_ids.length} entities)`);
      router.push("/solutions");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create solution");
    }
  }

  // Auto-included objects = resolved minus those the user explicitly picked.
  const autoIncluded = resolvedObjects.filter((s) => !draft.business_objects.includes(s));

  const canNext =
    (stepIndex === 0 && !!draft.solution_type) ||
    (stepIndex === 1 && true) || // industry is optional
    (stepIndex === 2 && draft.business_objects.length > 0) ||
    stepIndex >= 3;

  return (
    <div className="space-y-6">
      <Stepper steps={STEPS} current={stepIndex} />

      {stepIndex === 0 && (
        <ChooseTypeStep types={options.solution_types} selected={draft.solution_type} onSelect={chooseType} />
      )}
      {stepIndex === 1 && (
        <IndustryStep
          industries={options.industries}
          selected={draft.industry}
          onSelect={chooseIndustry}
        />
      )}
      {stepIndex === 2 && (
        <BuildingBlocksStep
          library={options.library}
          draft={draft}
          autoIncluded={autoIncluded}
          resolving={resolve.isPending}
          onToggle={(group, key) =>
            setDraft((d) => ({ ...d, [group]: toggle(d[group], key) }) as Draft)
          }
        />
      )}
      {stepIndex === 3 && (
        <ConfigureStep initial={draft.config} solutionType={draft.solution_type} onSubmit={setConfig} />
      )}
      {stepIndex === 4 && (
        <PreviewStep
          loading={preview.isPending}
          error={preview.isError}
          data={previewData}
          onRetry={() => void runPreview(selection)}
        />
      )}
      {stepIndex === 5 && (
        <CreateStep
          summary={previewData?.summary ?? null}
          creating={create.isPending}
          failed={create.isError}
          onCreate={doCreate}
        />
      )}

      {/* The Configure step (3) submits via its own form; navigation is hidden there. */}
      {stepIndex !== 3 && (
        <div className="flex items-center justify-between">
          <Button
            variant="ghost"
            onClick={() => setStepIndex((i) => Math.max(0, i - 1))}
            disabled={stepIndex === 0}
          >
            Back
          </Button>
          {stepIndex < 4 ? (
            <Button onClick={() => setStepIndex((i) => i + 1)} disabled={!canNext}>
              Next
            </Button>
          ) : stepIndex === 4 ? (
            <Button
              onClick={() => setStepIndex(5)}
              disabled={preview.isPending || !previewData || !previewData.valid}
            >
              Continue
            </Button>
          ) : null}
        </div>
      )}
    </div>
  );
}

function toggle(list: string[], key: string): string[] {
  return list.includes(key) ? list.filter((x) => x !== key) : [...list, key];
}

/* ----------------------------- Step 1: Choose Type ----------------------------- */

export function ChooseTypeStep({
  types,
  selected,
  onSelect,
}: {
  types: WizardOptions["solution_types"];
  selected: string;
  onSelect: (key: string) => void;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-medium">Choose a solution type</h2>
        <p className="text-sm text-muted-foreground">
          We&apos;ll prefill the recommended building blocks — you can change everything later.
        </p>
      </div>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {types.map((t) => (
          <li key={t.key}>
            <button
              type="button"
              aria-pressed={selected === t.key}
              aria-label={`Select ${t.label}`}
              onClick={() => onSelect(t.key)}
              className={
                "flex h-full w-full flex-col items-start gap-1 rounded-lg border p-4 text-left transition-colors hover:bg-accent " +
                (selected === t.key ? "border-primary ring-1 ring-primary" : "")
              }
            >
              <span className="font-medium">{t.label}</span>
              <span className="text-xs text-muted-foreground">
                {t.recommends.business_objects.length} objects · {t.recommends.workflows.length} workflows
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/* ----------------------------- Step 2: Industry ----------------------------- */

export function IndustryStep({
  industries,
  selected,
  onSelect,
}: {
  industries: WizardOptions["industries"];
  selected: string | null;
  onSelect: (key: string | null) => void;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-medium">Industry preset (optional)</h2>
        <p className="text-sm text-muted-foreground">
          Tailor the building blocks for your industry, or skip to keep the type defaults.
        </p>
      </div>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <li>
          <button
            type="button"
            aria-pressed={selected === null}
            aria-label="Skip industry preset"
            onClick={() => onSelect(null)}
            className={
              "flex h-full w-full flex-col items-start gap-1 rounded-lg border border-dashed p-4 text-left transition-colors hover:bg-accent " +
              (selected === null ? "border-primary ring-1 ring-primary" : "")
            }
          >
            <span className="font-medium">No industry preset</span>
            <span className="text-xs text-muted-foreground">Keep the solution-type defaults</span>
          </button>
        </li>
        {industries.map((ind) => (
          <li key={ind.key}>
            <button
              type="button"
              aria-pressed={selected === ind.key}
              aria-label={`Select ${ind.label}`}
              onClick={() => onSelect(ind.key)}
              className={
                "flex h-full w-full flex-col items-start gap-1 rounded-lg border p-4 text-left transition-colors hover:bg-accent " +
                (selected === ind.key ? "border-primary ring-1 ring-primary" : "")
              }
            >
              <span className="font-medium">{ind.label}</span>
              <span className="text-xs text-muted-foreground">
                {ind.recommends.business_objects.length} objects recommended
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/* ------------------------- Step 3: Select Building Blocks ------------------------- */

function CheckGroup({
  title,
  items,
  selected,
  onToggle,
  labelOf,
}: {
  title: string;
  items: { key: string; label: string }[];
  selected: string[];
  onToggle: (key: string) => void;
  labelOf?: (key: string) => string;
}) {
  return (
    <fieldset className="space-y-2 rounded-lg border p-4">
      <legend className="px-1 text-sm font-medium">{title}</legend>
      {items.length === 0 ? (
        <p className="text-xs text-muted-foreground">None available.</p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2">
          {items.map((it) => {
            const checked = selected.includes(it.key);
            return (
              <li key={it.key} className="flex items-center gap-2">
                <Checkbox
                  id={`${title}-${it.key}`}
                  checked={checked}
                  onCheckedChange={() => onToggle(it.key)}
                  aria-label={`${title}: ${labelOf?.(it.key) ?? it.label}`}
                />
                <Label htmlFor={`${title}-${it.key}`} className="cursor-pointer">
                  {labelOf?.(it.key) ?? it.label}
                </Label>
              </li>
            );
          })}
        </ul>
      )}
    </fieldset>
  );
}

function asChoices(items: LibraryObject[]): { key: string; label: string }[] {
  return items.map((o) => ({ key: o.slug, label: o.plural_name || o.name || o.slug }));
}

export function BuildingBlocksStep({
  library,
  draft,
  autoIncluded,
  resolving,
  onToggle,
}: {
  library: WizardLibrary;
  draft: Draft;
  autoIncluded: string[];
  resolving: boolean;
  onToggle: (group: "business_objects" | "workflows" | "roles" | "dashboards" | "reports", key: string) => void;
}) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-medium">Select building blocks</h2>
        <p className="text-sm text-muted-foreground">
          Pick the objects, automations, roles, dashboards and reports to include.
        </p>
      </div>

      <CheckGroup
        title="Business objects"
        items={asChoices(library.business_objects)}
        selected={draft.business_objects}
        onToggle={(k) => onToggle("business_objects", k)}
      />

      {(autoIncluded.length > 0 || resolving) && (
        <div className="rounded-md border border-dashed p-3 text-xs" aria-label="Auto-included dependencies">
          <p className="mb-1 font-medium text-muted-foreground">
            {resolving ? "Resolving dependencies…" : "Auto-included (required by your selection)"}
          </p>
          <div className="flex flex-wrap gap-1">
            {autoIncluded.map((s) => (
              <Badge key={s} variant="secondary">
                {s}
              </Badge>
            ))}
          </div>
        </div>
      )}

      <CheckGroup
        title="Workflows"
        items={asChoices(library.workflows)}
        selected={draft.workflows}
        onToggle={(k) => onToggle("workflows", k)}
      />
      <CheckGroup
        title="Roles"
        items={asChoices(library.roles)}
        selected={draft.roles}
        onToggle={(k) => onToggle("roles", k)}
      />
      <CheckGroup
        title="Dashboards"
        items={asChoices(library.dashboards)}
        selected={draft.dashboards}
        onToggle={(k) => onToggle("dashboards", k)}
      />
      <CheckGroup
        title="Reports"
        items={REPORT_KEYS.map((k) => ({ key: k, label: REPORT_LABELS[k] }))}
        selected={draft.reports}
        onToggle={(k) => onToggle("reports", k)}
      />
    </section>
  );
}

/* ----------------------------- Step 4: Configure ----------------------------- */

const configSchema = z.object({
  solution_name: z.string().min(1, "A solution name is required"),
  application_name: z.string().min(1, "An application name is required"),
  description: z.string(),
  icon: z.string(),
  color: z.string(),
});
type ConfigValues = z.infer<typeof configSchema>;

export function ConfigureStep({
  initial,
  solutionType,
  onSubmit,
}: {
  initial: WizardConfig;
  solutionType: string;
  onSubmit: (config: WizardConfig) => void;
}) {
  const form = useForm<ConfigValues>({
    resolver: zodResolver(configSchema),
    defaultValues: {
      solution_name: initial.solution_name,
      application_name: initial.application_name,
      description: initial.description,
      icon: initial.icon || "LayoutGrid",
      color: initial.color || "#2563eb",
    },
  });

  // Default the application name from the solution name until the user edits it.
  const solutionName = form.watch("solution_name");
  const appTouched = form.formState.dirtyFields.application_name;
  useEffect(() => {
    if (!appTouched) form.setValue("application_name", solutionName);
  }, [solutionName, appTouched, form]);

  return (
    <form
      className="max-w-lg space-y-4"
      onSubmit={form.handleSubmit((v) => onSubmit(v))}
      aria-label="Configure solution"
    >
      <div>
        <h2 className="text-lg font-medium">Configure</h2>
        <p className="text-sm text-muted-foreground">Name and brand the {solutionType || "solution"}.</p>
      </div>

      <div className="space-y-1">
        <Label htmlFor="solution_name">Solution name</Label>
        <Input id="solution_name" {...form.register("solution_name")} />
        {form.formState.errors.solution_name && (
          <p className="text-xs text-destructive">{form.formState.errors.solution_name.message}</p>
        )}
      </div>

      <div className="space-y-1">
        <Label htmlFor="application_name">Application name</Label>
        <Input id="application_name" {...form.register("application_name")} />
        {form.formState.errors.application_name && (
          <p className="text-xs text-destructive">{form.formState.errors.application_name.message}</p>
        )}
      </div>

      <div className="space-y-1">
        <Label htmlFor="description">Description</Label>
        <Textarea id="description" {...form.register("description")} />
      </div>

      <div className="flex gap-4">
        <div className="flex-1 space-y-1">
          <Label htmlFor="icon">Icon</Label>
          <Input id="icon" placeholder="LayoutGrid" {...form.register("icon")} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="color">Theme color</Label>
          <Input id="color" type="color" className="h-10 w-16 p-1" {...form.register("color")} />
        </div>
      </div>

      <Button type="submit">Preview solution</Button>
    </form>
  );
}

/* ----------------------------- Step 5: Preview ----------------------------- */

export function PreviewStep({
  loading,
  error,
  data,
  onRetry,
}: {
  loading: boolean;
  error: boolean;
  data: WizardPreview | null;
  onRetry: () => void;
}) {
  if (loading) return <Skeleton className="h-48 w-full" />;
  if (error) return <ErrorState title="Couldn't build the preview" action={{ label: "Retry", onClick: onRetry }} />;
  if (!data) return <ErrorState title="No preview yet" action={{ label: "Build preview", onClick: onRetry }} />;

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-medium">Preview</h2>
        <p className="text-sm text-muted-foreground">Nothing is installed yet. Review what will be provisioned.</p>
      </div>

      <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
        {SUMMARY_LABELS.map(({ key, label }) => (
          <div key={key} aria-label={label} className="rounded-md border p-2 text-center">
            <div className="text-lg font-semibold tabular-nums">{data.summary[key]}</div>
            <div className="text-xs text-muted-foreground">{label}</div>
          </div>
        ))}
      </div>

      {data.resolved_objects.length > 0 && (
        <div className="rounded-md border border-dashed p-3 text-xs">
          <p className="mb-1 font-medium text-muted-foreground">Resolved objects</p>
          <div className="flex flex-wrap gap-1">
            {data.resolved_objects.map((s) => (
              <Badge key={s} variant="secondary">
                {s}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {data.warnings.length > 0 && (
        <div role="status" className="space-y-1 rounded-md border border-amber-500/40 p-3 text-xs text-amber-700 dark:text-amber-400">
          <p className="font-medium">Warnings</p>
          {data.warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </div>
      )}

      {!data.valid && (
        <div role="alert" className="space-y-1 rounded-md border border-destructive/40 p-3 text-xs text-destructive">
          <p className="font-medium">This solution can&apos;t be created:</p>
          {data.errors.map((e) => (
            <p key={e}>{e}</p>
          ))}
        </div>
      )}
    </section>
  );
}

/* ----------------------------- Step 6: Create ----------------------------- */

export function CreateStep({
  summary,
  creating,
  failed,
  onCreate,
}: {
  summary: PreviewSummary | null;
  creating: boolean;
  failed: boolean;
  onCreate: () => void;
}) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-medium">Create solution</h2>
        <p className="text-sm text-muted-foreground">
          This provisions {summary ? `${summary.entities} entities, ${summary.workflows} workflows` : "the selected blocks"}{" "}
          and more into your workspace.
        </p>
      </div>

      {failed && (
        <div role="alert" className="rounded-md border border-destructive/40 p-3 text-xs text-destructive">
          Creation failed. You can safely retry.
        </div>
      )}

      <Button onClick={onCreate} disabled={creating}>
        {creating ? "Creating…" : failed ? "Retry create" : "Create solution"}
      </Button>
    </section>
  );
}
