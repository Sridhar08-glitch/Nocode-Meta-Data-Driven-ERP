import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  DryRunResult,
  Environment,
  ExecuteResponse,
  PromotionDashboard,
  PromotionPackage,
} from "@/lib/environments/api";

// ---- mocked hooks ----
type Q<T> = { isLoading: boolean; isError: boolean; data?: T };
type M<A, R> = { mutateAsync: (a: A) => Promise<R>; isPending: boolean };

const envs: Environment[] = [
  { id: "e-dev", name: "dev", env_type: "dev", branch: "env/dev", sequence: 1, is_production: false, status: "ready" },
  { id: "e-test", name: "test", env_type: "test", branch: "env/test", sequence: 2, is_production: false, status: "ready" },
  { id: "e-uat", name: "uat", env_type: "uat", branch: "env/uat", sequence: 3, is_production: false, status: "ready" },
  { id: "e-prod", name: "prod", env_type: "prod", branch: "env/prod", sequence: 4, is_production: true, status: "ready" },
];

const envQ: Q<Environment[]> = { isLoading: false, isError: false, data: envs };
const ensure: M<void, Environment[]> = { mutateAsync: vi.fn(() => Promise.resolve(envs)), isPending: false };
const dashQ: Q<PromotionDashboard> = { isLoading: false, isError: false, data: undefined };
const pkgsQ: Q<PromotionPackage[]> = { isLoading: false, isError: false, data: [] };
const create: M<unknown, PromotionPackage> = {
  mutateAsync: vi.fn(() => Promise.resolve({} as PromotionPackage)),
  isPending: false,
};
const pkgQ: Q<PromotionPackage> = { isLoading: false, isError: false, data: undefined };
const approve: M<string, PromotionPackage> = {
  mutateAsync: vi.fn(() => Promise.resolve({} as PromotionPackage)),
  isPending: false,
};
const execute: M<boolean, ExecuteResponse> = {
  mutateAsync: vi.fn(() => Promise.resolve({} as ExecuteResponse)),
  isPending: false,
};
const rollback: M<void, PromotionPackage> = {
  mutateAsync: vi.fn(() => Promise.resolve({} as PromotionPackage)),
  isPending: false,
};

vi.mock("@/lib/environments/hooks", () => ({
  useEnvironments: () => envQ,
  useEnsureEnvironments: () => ensure,
  usePromotionDashboard: () => dashQ,
  usePackages: () => pkgsQ,
  useCreatePackage: () => create,
  usePackage: () => pkgQ,
  useApprovePackage: () => approve,
  useExecutePackage: () => execute,
  useRollbackPackage: () => rollback,
}));

const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  toast: { success: (m: string) => toastSuccess(m), error: (m: string) => toastError(m) },
}));

import {
  CreatePackageForm,
  EnvironmentsStrip,
  PackageDetail,
  PackagesList,
  PromotionDashboardCard,
  ReleaseConsole,
} from "./release-console";

const mut = <A,>(fn: { mutateAsync: (a: A) => unknown }) => fn.mutateAsync as unknown as ReturnType<typeof vi.fn>;

function pkg(over: Partial<PromotionPackage> = {}): PromotionPackage {
  return {
    id: "p1",
    name: "Release 1",
    version: "1",
    source_env_id: "e-dev",
    target_env_id: "e-test",
    status: "approved",
    object_refs: [],
    diff: {},
    risk_summary: { low: 2, high: 1 },
    precheck: null,
    package_hash: "abcdef1234567890",
    merge_commit_sha: null,
    created_by: null,
    approved_by: null,
    executed_by: null,
    started_at: null,
    ended_at: null,
    approvals: [],
    ...over,
  };
}

beforeEach(() => {
  envQ.data = envs;
  dashQ.data = undefined;
  pkgsQ.data = [];
  pkgQ.data = undefined;
  vi.clearAllMocks();
});

describe("EnvironmentsStrip", () => {
  it("renders the DEV→TEST→UAT→PROD chain with branch names", () => {
    render(<EnvironmentsStrip isAdmin={false} />);
    expect(screen.getByText("dev")).toBeInTheDocument();
    expect(screen.getByText("env/dev")).toBeInTheDocument();
    expect(screen.getByText("env/uat")).toBeInTheDocument();
    expect(screen.getByText("env/prod")).toBeInTheDocument();
  });

  it("provisions environments on Set up (admin) → ensure mutateAsync called", async () => {
    render(<EnvironmentsStrip isAdmin />);
    fireEvent.click(screen.getByRole("button", { name: "Set up environments" }));
    await waitFor(() => expect(mut(ensure)).toHaveBeenCalled());
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith("Environments provisioned"));
  });

  it("hides the provision button for non-admins", () => {
    render(<EnvironmentsStrip isAdmin={false} />);
    expect(screen.queryByRole("button", { name: "Set up environments" })).not.toBeInTheDocument();
  });
});

describe("PromotionDashboardCard", () => {
  it("renders success rate, counts, and risk distribution from data", () => {
    dashQ.data = {
      by_status: { approved: 2 },
      pending: 3,
      approved: 2,
      rollbacks: 1,
      success_rate: 0.75,
      risk_distribution: { low: 4, medium: 2, high: 1, critical: 0 },
      release_velocity: 5,
    };
    render(<PromotionDashboardCard />);
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    const risk = screen.getByLabelText("Risk summary");
    expect(risk).toHaveTextContent("high: 1");
    expect(risk).toHaveTextContent("low: 4");
    // critical=0 is not rendered
    expect(risk).not.toHaveTextContent("critical");
  });
});

describe("CreatePackageForm", () => {
  it("sends source/target/name + objects payload and renders diff + risk", async () => {
    create.mutateAsync = vi.fn(() =>
      Promise.resolve(
        pkg({
          status: "precheck",
          risk_summary: { medium: 1, blocked: 1 },
          diff: { entities: { added: [{ slug: "lead" }], removed: [], modified: [] } },
        }),
      ),
    );
    render(<CreatePackageForm />);

    fireEvent.click(screen.getByRole("combobox", { name: "Source" }));
    fireEvent.click(await screen.findByRole("option", { name: "DEV (env/dev)" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Target" }));
    fireEvent.click(await screen.findByRole("option", { name: "TEST (env/test)" }));
    fireEvent.change(screen.getByLabelText("Package name"), { target: { value: "Release 1" } });

    fireEvent.click(screen.getByRole("button", { name: "Create package" }));

    await waitFor(() =>
      expect(mut(create)).toHaveBeenCalledWith({
        source_env_id: "e-dev",
        target_env_id: "e-test",
        name: "Release 1",
        objects: [],
      }),
    );
    expect(await screen.findByText("precheck blocked")).toBeInTheDocument();
    expect(screen.getByLabelText("diff-entities")).toHaveTextContent("lead");
  });

  it("includes added object rows in the payload", async () => {
    render(<CreatePackageForm />);
    fireEvent.click(screen.getByRole("combobox", { name: "Source" }));
    fireEvent.click(await screen.findByRole("option", { name: "DEV (env/dev)" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Target" }));
    fireEvent.click(await screen.findByRole("option", { name: "UAT (env/uat)" }));
    fireEvent.change(screen.getByLabelText("Package name"), { target: { value: "R2" } });
    fireEvent.click(screen.getByRole("button", { name: "Add object" }));
    fireEvent.change(screen.getByLabelText("Object 1 type"), { target: { value: "entity" } });
    fireEvent.change(screen.getByLabelText("Object 1 id"), { target: { value: "u-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create package" }));

    await waitFor(() =>
      expect(mut(create)).toHaveBeenCalledWith({
        source_env_id: "e-dev",
        target_env_id: "e-uat",
        name: "R2",
        objects: [{ object_type: "entity", object_id: "u-1" }],
      }),
    );
  });

  it("blocks create when source equals target", async () => {
    render(<CreatePackageForm />);
    fireEvent.click(screen.getByRole("combobox", { name: "Source" }));
    fireEvent.click(await screen.findByRole("option", { name: "DEV (env/dev)" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Target" }));
    fireEvent.click(await screen.findByRole("option", { name: "DEV (env/dev)" }));
    fireEvent.change(screen.getByLabelText("Package name"), { target: { value: "R" } });
    expect(screen.getByRole("alert")).toHaveTextContent(/must differ/);
    expect(screen.getByRole("button", { name: "Create package" })).toBeDisabled();
  });
});

describe("PackagesList", () => {
  it("renders status + risk badges and short hash; row selects", () => {
    pkgsQ.data = [pkg({ status: "executed", package_hash: "0011223344556677" })];
    const onSelect = vi.fn();
    render(<PackagesList envs={envs} selectedId={null} onSelect={onSelect} />);
    expect(screen.getByLabelText("Status: executed")).toBeInTheDocument();
    expect(screen.getByText("00112233")).toBeInTheDocument();
    expect(screen.getByLabelText("Risk: high")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Package Release 1" }));
    expect(onSelect).toHaveBeenCalledWith("p1");
  });

  it("renders an empty state when there are no packages", () => {
    pkgsQ.data = [];
    render(<PackagesList envs={envs} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByText("No packages yet")).toBeInTheDocument();
  });
});

describe("PackageDetail lifecycle", () => {
  it("approve sends {role} and surfaces SoD 400 via toast", async () => {
    pkgQ.data = pkg({ status: "precheck" });
    const { ApiError } = await import("@/lib/api/errors");
    approve.mutateAsync = vi.fn(() =>
      Promise.reject(new ApiError({ status: 400, message: "Creator cannot approve their own package" })),
    );
    render(<PackageDetail id="p1" isAdmin />);

    // pick role
    fireEvent.click(screen.getByRole("combobox", { name: "Approve as" }));
    fireEvent.click(await screen.findByRole("option", { name: "approver" }));
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(mut(approve)).toHaveBeenCalledWith("approver"));
    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Creator cannot approve their own package"),
    );
  });

  it("dry-run calls execute with dry_run=true and shows would-merge", async () => {
    pkgQ.data = pkg({ status: "approved" });
    const dry: DryRunResult = {
      dry_run: true,
      would_merge: true,
      target_sha_before: " feed00",
      risk: { low: 1 },
      diff: {},
    };
    execute.mutateAsync = vi.fn(() => Promise.resolve(dry));
    render(<PackageDetail id="p1" isAdmin />);
    fireEvent.click(screen.getByRole("button", { name: "Dry-run" }));
    await waitFor(() => expect(mut(execute)).toHaveBeenCalledWith(true));
    expect(await screen.findByLabelText("Dry-run result")).toHaveTextContent("Would merge cleanly");
  });

  it("promote calls execute with dry_run=false", async () => {
    pkgQ.data = pkg({ status: "approved" });
    execute.mutateAsync = vi.fn(() =>
      Promise.resolve({ status: "executed", merge_commit: "m1" } as ExecuteResponse),
    );
    render(<PackageDetail id="p1" isAdmin />);
    fireEvent.click(screen.getByRole("button", { name: "Promote" }));
    await waitFor(() => expect(mut(execute)).toHaveBeenCalledWith(false));
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith("Promoted"));
  });

  it("surfaces the critical-block 400 from execute via toast", async () => {
    pkgQ.data = pkg({ status: "approved" });
    const { ApiError } = await import("@/lib/api/errors");
    execute.mutateAsync = vi.fn(() =>
      Promise.reject(new ApiError({ status: 400, message: "Critical risk blocks promotion" })),
    );
    render(<PackageDetail id="p1" isAdmin />);
    fireEvent.click(screen.getByRole("button", { name: "Promote" }));
    await waitFor(() => expect(toastError).toHaveBeenCalledWith("Critical risk blocks promotion"));
  });

  it("rollback calls rollback mutateAsync", async () => {
    pkgQ.data = pkg({ status: "executed" });
    rollback.mutateAsync = vi.fn(() => Promise.resolve(pkg({ status: "rolled_back" })));
    render(<PackageDetail id="p1" isAdmin />);
    fireEvent.click(screen.getByRole("button", { name: "Rollback" }));
    await waitFor(() => expect(mut(rollback)).toHaveBeenCalled());
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith("Rolled back"));
  });

  it("button state is status-aware: approved → Promote enabled, Approve/Rollback disabled", () => {
    pkgQ.data = pkg({ status: "approved" });
    render(<PackageDetail id="p1" isAdmin />);
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Promote" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Dry-run" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Rollback" })).toBeDisabled();
  });

  it("button state: executed → Rollback enabled, Promote disabled", () => {
    pkgQ.data = pkg({ status: "executed" });
    render(<PackageDetail id="p1" isAdmin />);
    expect(screen.getByRole("button", { name: "Rollback" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Promote" })).toBeDisabled();
  });

  it("hides lifecycle actions for non-admins", () => {
    pkgQ.data = pkg({ status: "approved" });
    render(<PackageDetail id="p1" isAdmin={false} />);
    expect(screen.queryByText("Lifecycle")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Promote" })).not.toBeInTheDocument();
  });
});

describe("ReleaseConsole admin gating", () => {
  it("hides the dashboard + create form for non-admins", () => {
    render(<ReleaseConsole isAdmin={false} />);
    expect(screen.queryByText("Release dashboard")).not.toBeInTheDocument();
    expect(screen.queryByText("Create promotion package")).not.toBeInTheDocument();
    // environments + packages list still show
    expect(screen.getByText("Environments")).toBeInTheDocument();
    expect(screen.getByText("Promotion packages")).toBeInTheDocument();
  });

  it("shows admin surfaces for admins", () => {
    dashQ.data = {
      by_status: {},
      pending: 0,
      approved: 0,
      rollbacks: 0,
      success_rate: 1,
      risk_distribution: { low: 0, medium: 0, high: 0, critical: 0 },
      release_velocity: 0,
    };
    render(<ReleaseConsole isAdmin />);
    expect(screen.getByText("Release dashboard")).toBeInTheDocument();
    expect(screen.getByText("Create promotion package")).toBeInTheDocument();
  });
});
