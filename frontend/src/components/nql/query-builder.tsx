"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  addToGroup,
  describe as describeQuery,
  emptyCondition,
  emptyGroup,
  removeAt,
  setGroupOp,
  updateCondition,
} from "@/lib/nql/builder";
import {
  type ComparisonOp,
  COMPARISON_OPTIONS,
  type Condition,
  type FilterNode,
  type GroupOp,
  GROUP_OP_OPTIONS,
  isGroup,
  isListOp,
  isNullaryOp,
  MAGIC_VALUES,
  type NqlQuery,
  type SortDirection,
} from "@/lib/nql/types";

export interface FieldOption {
  slug: string;
  name: string;
}

export interface QueryBuilderProps {
  fields: FieldOption[];
  value: NqlQuery;
  onChange: (next: NqlQuery) => void;
}

/**
 * Visual NQL query builder (Phase F1.9): recursive AND/OR filter groups, sort clauses, and a live
 * "view as NQL" panel. Emits the wire AST via `onChange`; the parent runs/serializes it.
 */
export function QueryBuilder({ fields, value, onChange }: QueryBuilderProps) {
  const root = value.filter ?? emptyGroup("and");

  const setFilter = (next: FilterNode) => onChange({ ...value, filter: next });

  return (
    <div className="space-y-5">
      <section className="space-y-2">
        <h3 className="text-sm font-medium text-muted-foreground">Filters</h3>
        <GroupEditor node={root} path={[]} fields={fields} onChange={setFilter} root={root} />
      </section>

      <SortEditor fields={fields} value={value} onChange={onChange} />

      <section className="space-y-2">
        <h3 className="text-sm font-medium text-muted-foreground">View as NQL</h3>
        <pre
          aria-label="NQL preview"
          className="overflow-x-auto rounded-md border bg-muted/40 p-3 font-mono text-xs"
        >
          {describeQuery(value)}
        </pre>
      </section>
    </div>
  );
}

function GroupEditor({
  node,
  path,
  fields,
  onChange,
  root,
}: {
  node: FilterNode;
  path: number[];
  fields: FieldOption[];
  onChange: (next: FilterNode) => void;
  root: FilterNode;
}) {
  if (!isGroup(node)) return null;
  const update = (fn: (r: FilterNode) => FilterNode) => onChange(fn(root));

  return (
    <div className="space-y-2 rounded-md border border-dashed p-3">
      <div className="flex items-center gap-2">
        <Select
          value={node.op}
          onValueChange={(v) => update((r) => setGroupOp(r, path, v as GroupOp))}
        >
          <SelectTrigger aria-label="Match type" className="h-8 w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {GROUP_OP_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-xs text-muted-foreground">of the following</span>
        {path.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            aria-label="Remove group"
            onClick={() => update((r) => removeAt(r, path))}
          >
            ✕
          </Button>
        )}
      </div>

      <div className="space-y-2 pl-3">
        {node.conditions.map((child, i) =>
          isGroup(child) ? (
            <GroupEditor
              key={i}
              node={child}
              path={[...path, i]}
              fields={fields}
              onChange={onChange}
              root={root}
            />
          ) : (
            <ConditionEditor
              key={i}
              condition={child}
              path={[...path, i]}
              fields={fields}
              onChange={onChange}
              root={root}
            />
          ),
        )}
        {node.conditions.length === 0 && (
          <p className="text-xs text-muted-foreground">No conditions yet.</p>
        )}
      </div>

      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => update((r) => addToGroup(r, path, emptyCondition()))}
        >
          Add condition
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => update((r) => addToGroup(r, path, emptyGroup("and")))}
        >
          Add group
        </Button>
      </div>
    </div>
  );
}

function ConditionEditor({
  condition,
  path,
  fields,
  onChange,
  root,
}: {
  condition: Condition;
  path: number[];
  fields: FieldOption[];
  onChange: (next: FilterNode) => void;
  root: FilterNode;
}) {
  const update = (fn: (r: FilterNode) => FilterNode) => onChange(fn(root));
  const showValue = !isNullaryOp(condition.op);
  const list = isListOp(condition.op);
  const valueStr = Array.isArray(condition.value)
    ? condition.value.join(", ")
    : condition.value == null
      ? ""
      : String(condition.value);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select
        value={condition.field || undefined}
        onValueChange={(v) => update((r) => updateCondition(r, path, { field: v }))}
      >
        <SelectTrigger aria-label="Field" className="h-8 w-44">
          <SelectValue placeholder="Field" />
        </SelectTrigger>
        <SelectContent>
          {fields.map((f) => (
            <SelectItem key={f.slug} value={f.slug}>
              {f.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={condition.op}
        onValueChange={(v) => update((r) => updateCondition(r, path, { op: v as ComparisonOp }))}
      >
        <SelectTrigger aria-label="Operator" className="h-8 w-40">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {COMPARISON_OPTIONS.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {showValue && (
        <Input
          aria-label="Value"
          className="h-8 w-48"
          placeholder={list ? "a, b, c" : "value or @me"}
          value={valueStr}
          onChange={(e) =>
            update((r) =>
              updateCondition(r, path, {
                value: list ? e.target.value.split(",").map((s) => s.trim()) : e.target.value,
              }),
            )
          }
          list="nql-magic-values"
        />
      )}
      <datalist id="nql-magic-values">
        {MAGIC_VALUES.map((m) => (
          <option key={m.value} value={m.value}>
            {m.label}
          </option>
        ))}
      </datalist>

      <Button
        variant="ghost"
        size="sm"
        aria-label="Remove condition"
        onClick={() => update((r) => removeAt(r, path))}
      >
        ✕
      </Button>
    </div>
  );
}

function SortEditor({
  fields,
  value,
  onChange,
}: {
  fields: FieldOption[];
  value: NqlQuery;
  onChange: (next: NqlQuery) => void;
}) {
  const sort = value.sort ?? [];
  const setSort = (next: typeof sort) => onChange({ ...value, sort: next });

  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium text-muted-foreground">Sort</h3>
      {sort.map((s, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2">
          <Select
            value={s.field || undefined}
            onValueChange={(v) => setSort(sort.map((x, j) => (j === i ? { ...x, field: v } : x)))}
          >
            <SelectTrigger aria-label={`Sort field ${i + 1}`} className="h-8 w-44">
              <SelectValue placeholder="Field" />
            </SelectTrigger>
            <SelectContent>
              {fields.map((f) => (
                <SelectItem key={f.slug} value={f.slug}>
                  {f.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={s.direction}
            onValueChange={(v) =>
              setSort(sort.map((x, j) => (j === i ? { ...x, direction: v as SortDirection } : x)))
            }
          >
            <SelectTrigger aria-label={`Sort direction ${i + 1}`} className="h-8 w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="asc">Ascending</SelectItem>
              <SelectItem value="desc">Descending</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="ghost"
            size="sm"
            aria-label={`Remove sort ${i + 1}`}
            onClick={() => setSort(sort.filter((_, j) => j !== i))}
          >
            ✕
          </Button>
        </div>
      ))}
      <Label className="sr-only" htmlFor="add-sort">
        Add sort
      </Label>
      <Button
        id="add-sort"
        variant="outline"
        size="sm"
        onClick={() => setSort([...sort, { field: "", direction: "asc" }])}
      >
        Add sort
      </Button>
    </section>
  );
}
