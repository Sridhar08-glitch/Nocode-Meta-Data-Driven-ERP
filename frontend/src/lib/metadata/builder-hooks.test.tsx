import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./builder-api", () => ({
  builderApi: {
    createEntity: vi.fn(() => Promise.resolve({ slug: "lead" })),
    updateEntity: vi.fn(() => Promise.resolve({})),
    deleteEntity: vi.fn(() => Promise.resolve(null)),
    listFields: vi.fn(() => Promise.resolve([])),
    createField: vi.fn(() => Promise.resolve({})),
    updateField: vi.fn(() => Promise.resolve({})),
    deleteField: vi.fn(() => Promise.resolve(null)),
    promoteField: vi.fn(() => Promise.resolve({})),
    demoteField: vi.fn(() => Promise.resolve({})),
    listForms: vi.fn(() => Promise.resolve([])),
    getForm: vi.fn(() => Promise.resolve({})),
    createForm: vi.fn(() => Promise.resolve({})),
    updateForm: vi.fn(() => Promise.resolve({})),
    deleteForm: vi.fn(() => Promise.resolve(null)),
    schemaVersions: vi.fn(() => Promise.resolve([])),
    createModule: vi.fn(() => Promise.resolve({})),
    rollbackSchema: vi.fn(() => Promise.resolve({})),
  },
}));

import { builderApi } from "./builder-api";
import {
  useCreateEntity,
  useCreateField,
  useCreateForm,
  useCreateModule,
  useDeleteEntity,
  useDeleteField,
  useDeleteForm,
  useFields,
  useForm,
  useForms,
  usePromoteField,
  useRollbackSchema,
  useSchemaVersions,
  useUpdateEntity,
  useUpdateField,
  useUpdateForm,
} from "./builder-hooks";

function wrap() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = "W";
  return { qc, wrapper: Wrapper };
}

beforeEach(() => {
  tenant.workspace = { slug: "acme" };
  tenant.isReady = true;
  vi.clearAllMocks();
});

describe("builder query hooks", () => {
  it("useFields fetches when scoped", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useFields("lead"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(builderApi.listFields).toHaveBeenCalledWith("lead");
  });

  it("useFields is disabled without a workspace", () => {
    tenant.workspace = null;
    const { wrapper } = wrap();
    const { result } = renderHook(() => useFields("lead"), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
    expect(builderApi.listFields).not.toHaveBeenCalled();
  });

  it("useForms / useForm / useSchemaVersions fetch when scoped", async () => {
    const { wrapper } = wrap();
    const forms = renderHook(() => useForms("lead"), { wrapper });
    const one = renderHook(() => useForm("lead", "f1"), { wrapper });
    const versions = renderHook(() => useSchemaVersions("lead"), { wrapper });
    await waitFor(() => expect(forms.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(one.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(versions.result.current.isSuccess).toBe(true));
    expect(builderApi.listForms).toHaveBeenCalledWith("lead");
    expect(builderApi.getForm).toHaveBeenCalledWith("lead", "f1");
    expect(builderApi.schemaVersions).toHaveBeenCalledWith("lead");
  });
});

describe("builder mutation hooks", () => {
  it("useCreateEntity calls the API and invalidates meta", async () => {
    const { qc, wrapper } = wrap();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useCreateEntity(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ slug: "lead", name: "Lead", plural_name: "Leads" });
    });
    expect(builderApi.createEntity).toHaveBeenCalled();
    expect(spy).toHaveBeenCalledWith({ queryKey: ["meta", "acme"] });
  });

  it("useDeleteEntity calls deleteEntity", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useDeleteEntity(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync("lead");
    });
    expect(builderApi.deleteEntity).toHaveBeenCalledWith("lead");
  });

  it("useCreateField scopes to the entity", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useCreateField("lead"), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ slug: "name", name: "Name", field_type: "text" });
    });
    expect(builderApi.createField).toHaveBeenCalledWith("lead", {
      slug: "name",
      name: "Name",
      field_type: "text",
    });
  });

  it("useUpdateField threads field slug + data", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useUpdateField("lead"), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ fieldSlug: "name", data: { is_required: true } });
    });
    expect(builderApi.updateField).toHaveBeenCalledWith("lead", "name", { is_required: true });
  });

  it("usePromoteField routes to promote/demote by flag", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => usePromoteField("lead"), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ fieldSlug: "name", promote: true });
    });
    expect(builderApi.promoteField).toHaveBeenCalledWith("lead", "name");
    await act(async () => {
      await result.current.mutateAsync({ fieldSlug: "name", promote: false });
    });
    expect(builderApi.demoteField).toHaveBeenCalledWith("lead", "name");
  });

  it("useRollbackSchema calls rollback with the version", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useRollbackSchema("lead"), { wrapper });
    await act(async () => {
      await result.current.mutateAsync(2);
    });
    expect(builderApi.rollbackSchema).toHaveBeenCalledWith("lead", 2);
  });

  it("useUpdateEntity threads the entity slug", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useUpdateEntity("lead"), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ name: "Leads" });
    });
    expect(builderApi.updateEntity).toHaveBeenCalledWith("lead", { name: "Leads" });
  });

  it("form mutations route to the entity-scoped API", async () => {
    const { wrapper } = wrap();
    const c = renderHook(() => useCreateForm("lead"), { wrapper });
    const u = renderHook(() => useUpdateForm("lead"), { wrapper });
    const d = renderHook(() => useDeleteForm("lead"), { wrapper });
    await act(async () => {
      await c.result.current.mutateAsync({ name: "Intake" });
      await u.result.current.mutateAsync({ formId: "f1", data: { name: "Intake 2" } });
      await d.result.current.mutateAsync("f1");
    });
    expect(builderApi.createForm).toHaveBeenCalledWith("lead", { name: "Intake" });
    expect(builderApi.updateForm).toHaveBeenCalledWith("lead", "f1", { name: "Intake 2" });
    expect(builderApi.deleteForm).toHaveBeenCalledWith("lead", "f1");
  });

  it("useDeleteField calls deleteField", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useDeleteField("lead"), { wrapper });
    await act(async () => {
      await result.current.mutateAsync("name");
    });
    expect(builderApi.deleteField).toHaveBeenCalledWith("lead", "name");
  });

  it("useCreateModule calls createModule", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useCreateModule(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ name: "Sales" });
    });
    expect(builderApi.createModule).toHaveBeenCalledWith({ name: "Sales" });
  });
});
