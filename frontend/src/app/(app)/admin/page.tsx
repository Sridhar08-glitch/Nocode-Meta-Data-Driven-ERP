"use client";

import Link from "next/link";

import { TenantHealthPanel } from "@/components/admin/tenant-health";

const SECTIONS: { href: string; label: string; description: string }[] = [
  { href: "/admin/members", label: "Members", description: "Invite teammates, assign roles, suspend/remove, transfer ownership." },
  { href: "/admin/workspace", label: "Workspace settings", description: "Workspace name, plan, and limits." },
  { href: "/admin/health", label: "Tenant health", description: "Workflow, activity, error, storage, and SLA KPIs." },
  { href: "/admin/audit", label: "Audit log", description: "Immutable, filterable event history." },
  { href: "/admin/config-vcs", label: "Configuration history", description: "Commit, diff, and roll back config." },
  { href: "/admin/promotions", label: "Environment promotions", description: "Promote config DEV→TEST→UAT→PROD with approvals." },
  { href: "/admin/lineage", label: "Data lineage", description: "Upstream/downstream impact analysis." },
  { href: "/admin/dependencies", label: "Dependencies & impact", description: "What depends on an object; change/delete safety." },
  { href: "/admin/certification", label: "Enterprise certification", description: "Cross-module integration health, architecture validation, simulations." },
  { href: "/admin/backups", label: "Backups & restore", description: "Backups + point-in-time restore to an isolated target." },
  { href: "/admin/marketplace", label: "Marketplace", description: "Browse, install, upgrade, and roll back plugins." },
  { href: "/admin/recycle-bin", label: "Recycle bin", description: "Restore or purge deleted records." },
  { href: "/admin/portal", label: "External portal", description: "Configure the portal, users, and entity grants." },
  { href: "/admin/branding", label: "Branding", description: "White-label colors, logo, custom CSS, SMTP." },
  { href: "/admin/localization", label: "Localization", description: "Default locale, timezone, currency, entity labels." },
  { href: "/admin/numbering", label: "Numbering", description: "Gapless document number sequences (INV-, PO-, JE-…)." },
  { href: "/permissions", label: "Permissions", description: "Roles, RBAC/ABAC grants, field masking." },
  { href: "/feature-flags", label: "Feature flags", description: "Modules, betas, %-rollout, overrides." },
  { href: "/studio", label: "Studio", description: "Entities, fields, forms, applications, navigation." },
  { href: "/workflows", label: "Workflows", description: "Automation graphs + run monitor." },
  { href: "/rules", label: "Rules", description: "Record-save field changes + save-blocks." },
  { href: "/reports", label: "Reports", description: "NQL reports, snapshots, exports." },
  { href: "/catalog", label: "Process catalog", description: "Install packaged business processes." },
  { href: "/settings/sessions", label: "Sessions", description: "Active sessions for your account." },
];

export default function AdminPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Admin</h1>
        <p className="text-sm text-muted-foreground">Tenant health and workspace administration.</p>
      </div>

      <TenantHealthPanel />

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">Manage</h2>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {SECTIONS.map((s) => (
            <li key={s.href}>
              <Link
                href={s.href}
                className="flex h-full flex-col gap-1 rounded-lg border p-4 transition-colors hover:bg-accent"
              >
                <span className="font-medium">{s.label}</span>
                <span className="text-xs text-muted-foreground">{s.description}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
