"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ABAC_OP_OPTIONS,
  ABAC_USER_TOKENS,
  type AbacCondition,
  type AbacOp,
} from "@/lib/permissions/api";

const NULLARY = new Set<AbacOp>(["is null", "is not null"]);

/** Editor for an ABAC condition list ([{field, op, value}], `$user.*` tokens supported). */
export function AbacConditions({
  value,
  onChange,
}: {
  value: AbacCondition[];
  onChange: (next: AbacCondition[]) => void;
}) {
  const set = (i: number, patch: Partial<AbacCondition>) =>
    onChange(value.map((c, j) => (j === i ? { ...c, ...patch } : c)));

  return (
    <div className="space-y-2">
      {value.map((c, i) => {
        const showValue = !NULLARY.has(c.op);
        return (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <Input
              aria-label={`Condition field ${i + 1}`}
              className="h-8 w-40"
              placeholder="owner_id"
              value={c.field}
              onChange={(e) => set(i, { field: e.target.value })}
            />
            <Select value={c.op} onValueChange={(v) => set(i, { op: v as AbacOp })}>
              <SelectTrigger aria-label={`Condition operator ${i + 1}`} className="h-8 w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ABAC_OP_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {showValue && (
              <Input
                aria-label={`Condition value ${i + 1}`}
                className="h-8 w-44"
                placeholder="$user.id"
                value={c.value === undefined ? "" : String(c.value)}
                onChange={(e) => set(i, { value: e.target.value })}
                list="abac-user-tokens"
              />
            )}
            <Button
              variant="ghost"
              size="sm"
              aria-label={`Remove condition ${i + 1}`}
              onClick={() => onChange(value.filter((_, j) => j !== i))}
            >
              ✕
            </Button>
          </div>
        );
      })}
      <datalist id="abac-user-tokens">
        {ABAC_USER_TOKENS.map((t) => (
          <option key={t.value} value={t.value}>
            {t.label}
          </option>
        ))}
      </datalist>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onChange([...value, { field: "", op: "=", value: "$user.id" }])}
      >
        Add condition
      </Button>
    </div>
  );
}
