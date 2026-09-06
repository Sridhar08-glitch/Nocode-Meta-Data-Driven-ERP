/** Pure navigation-grouping logic (Phase F1.4) — entities grouped by module, with
 *  unreadable/inactive entities filtered out. Extracted so it's unit-testable. */
import type { EntityMeta, ModuleMeta } from "./types";

export interface NavGroup {
  module: ModuleMeta | null;
  entities: EntityMeta[];
}

function sortByName(list: EntityMeta[]): EntityMeta[] {
  return [...list].sort((a, b) => (a.plural_name || a.name).localeCompare(b.plural_name || b.name));
}

export function buildNavGroups(
  entities: EntityMeta[] | undefined,
  modules: ModuleMeta[] | undefined,
): NavGroup[] {
  // Permission-aware: drop inactive + entities the member can't read (can_read===false).
  const visible = (entities ?? []).filter((e) => e.is_active && e.can_read !== false);
  const orderedModules = (modules ?? [])
    .filter((m) => m.is_active)
    .sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));

  const byModule = new Map<string | null, EntityMeta[]>();
  for (const e of visible) {
    const key = e.module ?? null;
    const list = byModule.get(key) ?? [];
    list.push(e);
    byModule.set(key, list);
  }

  const groups: NavGroup[] = [];
  for (const m of orderedModules) {
    const ents = byModule.get(m.id);
    if (ents?.length) groups.push({ module: m, entities: sortByName(ents) });
  }
  const ungrouped = byModule.get(null);
  if (ungrouped?.length) groups.push({ module: null, entities: sortByName(ungrouped) });
  return groups;
}
