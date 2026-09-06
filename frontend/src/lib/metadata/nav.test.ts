import { describe, expect, it } from "vitest";

import { buildNavGroups } from "./nav";
import type { EntityMeta, ModuleMeta } from "./types";

const mod = (id: string, name: string, order = 0): ModuleMeta => ({
  id,
  name,
  slug: name.toLowerCase(),
  description: "",
  icon: "",
  color: "",
  is_active: true,
  order,
});

const ent = (slug: string, over: Partial<EntityMeta> = {}): EntityMeta => ({
  id: slug,
  slug,
  name: slug,
  plural_name: slug + "s",
  description: "",
  icon: "",
  color: "",
  module: null,
  is_active: true,
  title_field_slug: "name",
  current_schema_version: 1,
  fields: [],
  can_read: true,
  ...over,
});

describe("buildNavGroups", () => {
  it("groups entities under their module, ordered by module.order", () => {
    const modules = [mod("m2", "Sales", 2), mod("m1", "HR", 1)];
    const entities = [ent("lead", { module: "m2" }), ent("employee", { module: "m1" })];
    const groups = buildNavGroups(entities, modules);
    expect(groups.map((g) => g.module?.name)).toEqual(["HR", "Sales"]);
  });

  it("hides entities the member cannot read (can_read === false)", () => {
    const entities = [ent("lead", { can_read: true }), ent("salary", { can_read: false })];
    const groups = buildNavGroups(entities, []);
    const slugs = groups.flatMap((g) => g.entities.map((e) => e.slug));
    expect(slugs).toEqual(["lead"]);
    expect(slugs).not.toContain("salary");
  });

  it("treats undefined can_read as readable", () => {
    const groups = buildNavGroups([ent("lead", { can_read: undefined })], []);
    expect(groups[0].entities[0].slug).toBe("lead");
  });

  it("drops inactive entities and empty modules", () => {
    const modules = [mod("m1", "Empty"), mod("m2", "CRM")];
    const entities = [ent("lead", { module: "m2" }), ent("ghost", { module: "m2", is_active: false })];
    const groups = buildNavGroups(entities, modules);
    expect(groups).toHaveLength(1);
    expect(groups[0].module?.name).toBe("CRM");
    expect(groups[0].entities).toHaveLength(1);
  });

  it("puts module-less entities in a trailing 'Other' group", () => {
    const groups = buildNavGroups([ent("note")], [mod("m1", "CRM")]);
    expect(groups.at(-1)?.module).toBeNull();
    expect(groups.at(-1)?.entities[0].slug).toBe("note");
  });

  it("sorts entities within a group by plural name", () => {
    const groups = buildNavGroups([ent("zebra"), ent("apple")], []);
    expect(groups[0].entities.map((e) => e.slug)).toEqual(["apple", "zebra"]);
  });
});
