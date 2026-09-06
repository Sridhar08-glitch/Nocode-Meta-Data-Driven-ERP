/**
 * Rules client (Phase F2.4) — BusinessRule CRUD over `/api/v1/rules/`. A rule is an NQL condition
 * → an ordered action list, evaluated on record save (separate from workflows). The synchronous
 * engine implements `set_field` and `block_save`; entity binding is by `entity_id` (UUID).
 */
import { apiGet, apiSend } from "@/lib/api/request";

export type RuleTrigger =
  | "before_create"
  | "after_create"
  | "before_update"
  | "after_update"
  | "before_delete"
  | "after_delete"
  | "field_changed";

/** Action item: `{ type, ...flat config }`. Engine-supported types only. */
export type RuleActionType = "set_field" | "block_save";
export interface RuleAction {
  type: RuleActionType;
  field?: string;
  value?: unknown;
}

export interface BusinessRule {
  id: string;
  name: string;
  slug: string;
  description: string;
  entity_id: string | null;
  trigger_on: RuleTrigger;
  watch_field_slug: string;
  condition_nql: string;
  actions: RuleAction[];
  priority: number;
  run_all: boolean;
  is_active: boolean;
  is_system: boolean;
  eval_count: number;
  match_count: number;
  last_matched_at: string | null;
  created_at: string;
  updated_at: string;
}
export interface BusinessRuleWrite {
  name: string;
  slug: string;
  description?: string;
  entity_id?: string | null;
  trigger_on?: RuleTrigger;
  watch_field_slug?: string;
  condition_nql?: string;
  actions?: RuleAction[];
  priority?: number;
  run_all?: boolean;
  is_active?: boolean;
}
export interface Paged<T> {
  results: T[];
  count: number;
}

export const RULE_TRIGGER_OPTIONS: { value: RuleTrigger; label: string }[] = [
  { value: "before_create", label: "Before create" },
  { value: "after_create", label: "After create" },
  { value: "before_update", label: "Before update" },
  { value: "after_update", label: "After update" },
  { value: "before_delete", label: "Before delete" },
  { value: "after_delete", label: "After delete" },
  { value: "field_changed", label: "Field changed" },
];

/** Only these actions are honored by the backend engine. */
export const RULE_ACTION_OPTIONS: { value: RuleActionType; label: string }[] = [
  { value: "set_field", label: "Set a field" },
  { value: "block_save", label: "Block the save" },
];

const R = "/api/v1/rules";

export const rulesApi = {
  list: (entityId?: string) =>
    apiGet<Paged<BusinessRule>>(`${R}/${entityId ? `?entity_id=${encodeURIComponent(entityId)}` : ""}`),
  get: (id: string) => apiGet<BusinessRule>(`${R}/${id}/`),
  create: (data: BusinessRuleWrite) => apiSend<BusinessRule>(`${R}/`, "POST", data),
  update: (id: string, data: Partial<BusinessRuleWrite>) => apiSend<BusinessRule>(`${R}/${id}/`, "PATCH", data),
  remove: (id: string) => apiSend<null>(`${R}/${id}/`, "DELETE"),
};
