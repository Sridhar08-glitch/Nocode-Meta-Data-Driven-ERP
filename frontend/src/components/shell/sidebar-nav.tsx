"use client";

import { Activity, Banknote, BarChart3, BookOpen, Boxes, CalendarClock, CheckSquare, Code2, Factory, FileText, Flag, FolderKanban, FormInput, GitBranch, Home, LayoutDashboard, LayoutGrid, LifeBuoy, LineChart, Mail, Package, Search, Settings, ShieldCheck, ShoppingCart, Sparkles, Table2, Timer, UserCog, Users, Workflow, Wrench } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/states";
import { useI18n } from "@/lib/i18n/context";
import { useModules, useRuntimeEntities } from "@/lib/metadata/hooks";
import { buildNavGroups } from "@/lib/metadata/nav";
import { useInstalledSolutions } from "@/lib/solution-templates/hooks";
import { useTenant } from "@/lib/tenant/context";
import { useActiveApp } from "@/lib/studio/active-app";
import type { NavItem, ResolvedNavigation } from "@/lib/studio/api";
import { useResolvedNav } from "@/lib/studio/hooks";
import { cn } from "@/lib/utils";

/** href for a resolved-navigation item (entity → record list, internal/external → as given). */
function navItemHref(item: NavItem): string {
  if (item.type === "entity") return `/e/${item.target}`;
  return item.target;
}

function NavLink({
  href,
  label,
  active,
  icon: Icon = Table2,
}: {
  href: string;
  label: string;
  active: boolean;
  icon?: typeof Table2;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
        active ? "bg-primary/10 font-medium text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      <Icon className="size-4 shrink-0" />
      <span className="truncate">{label}</span>
    </Link>
  );
}

type Link = { href: string; key: string; label: string; icon: typeof Table2; exact?: boolean; adminOnly?: boolean };

/** Always-on platform tools — available regardless of which solutions are installed. */
const PLATFORM_LINKS: Link[] = [
  { href: "/home", key: "nav.home", label: "Home", icon: Home, exact: true },
  { href: "/studio", key: "nav.studio", label: "Studio", icon: Wrench, adminOnly: true },
  { href: "/query", key: "nav.query", label: "Query", icon: Search },
  { href: "/documents", key: "nav.documents", label: "Documents", icon: FileText },
  { href: "/public-forms", key: "nav.public_forms", label: "Public forms", icon: FormInput },
  { href: "/activity", key: "nav.activity", label: "Activity", icon: Activity },
];

/**
 * Domain-module links, each gated by the solution(s) that provide it. A module link
 * only appears when a matching solution is installed in the workspace — so installing
 * one package no longer shows every other module (incl. core CRM/Inventory/etc.).
 */
const MODULE_LINKS: (Link & { solutions: string[] })[] = [
  { href: "/accounting", key: "nav.accounting", label: "Accounting", icon: BookOpen, solutions: ["crm", "sales_crm", "hr", "payroll", "procurement", "manufacturing", "assets", "projects"] },
  { href: "/crm", key: "nav.crm", label: "CRM", icon: Users, solutions: ["crm", "sales_crm"] },
  { href: "/inventory", key: "nav.inventory", label: "Inventory", icon: Boxes, solutions: ["manufacturing", "procurement"] },
  { href: "/manufacturing", key: "nav.manufacturing", label: "Manufacturing", icon: Factory, solutions: ["manufacturing"] },
  { href: "/procurement", key: "nav.procurement", label: "Procurement", icon: ShoppingCart, solutions: ["procurement"] },
  { href: "/hr", key: "nav.hr", label: "HR", icon: UserCog, solutions: ["hr"] },
  { href: "/payroll", key: "nav.payroll", label: "Payroll", icon: Banknote, solutions: ["payroll"] },
  { href: "/assets", key: "nav.assets", label: "Assets", icon: Package, solutions: ["assets"] },
  { href: "/projects", key: "nav.projects", label: "Projects", icon: FolderKanban, solutions: ["projects"] },
  { href: "/helpdesk", key: "nav.helpdesk", label: "Helpdesk", icon: LifeBuoy, solutions: ["helpdesk"] },
  { href: "/analytics", key: "nav.analytics", label: "Analytics", icon: LineChart, solutions: ["analytics"] },
];

/**
 * Platform/back-office tools shown after the domain modules. Configuration &
 * administration tools are `adminOnly` — hidden from non-admin roles (e.g. a teacher,
 * accountant or student) so their sidebar only shows what they can actually use.
 */
const TOOL_LINKS: Link[] = [
  { href: "/reports", key: "nav.reports", label: "Reports", icon: BarChart3 },
  { href: "/dashboards", key: "nav.dashboards", label: "Dashboards", icon: LayoutDashboard },
  { href: "/workflows", key: "nav.workflows", label: "Workflows", icon: Workflow, adminOnly: true },
  { href: "/rules", key: "nav.rules", label: "Rules", icon: GitBranch, adminOnly: true },
  { href: "/approvals", key: "nav.approvals", label: "Approvals", icon: CheckSquare },
  { href: "/sla", key: "nav.slas", label: "SLAs", icon: Timer, adminOnly: true },
  { href: "/calendars", key: "nav.calendars", label: "Calendars", icon: CalendarClock, adminOnly: true },
  { href: "/templates", key: "nav.templates", label: "Templates", icon: Mail, adminOnly: true },
  { href: "/permissions", key: "nav.permissions", label: "Permissions", icon: ShieldCheck, adminOnly: true },
  { href: "/solutions", key: "nav.solutions", label: "Solutions", icon: LayoutGrid, adminOnly: true },
  { href: "/solutions/new", key: "nav.create_solution", label: "Create solution", icon: Sparkles, adminOnly: true },
  { href: "/catalog", key: "nav.catalog", label: "Process catalog", icon: Package, adminOnly: true },
  { href: "/feature-flags", key: "nav.feature_flags", label: "Feature flags", icon: Flag, adminOnly: true },
  { href: "/developer", key: "nav.developer", label: "Developer", icon: Code2, adminOnly: true },
  { href: "/admin", key: "nav.admin", label: "Admin", icon: Settings, adminOnly: true },
];

/** Metadata-driven, permission-filtered navigation: entities grouped by module. */
export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { t } = useI18n();
  // Runtime entities = metadata entities + system entities (B0.2), so native-model engines appear
  // in the nav and render through the Generic Runtime.
  const entitiesQuery = useRuntimeEntities();
  const modulesQuery = useModules();
  const installedQuery = useInstalledSolutions();
  const { workspace } = useTenant();
  const isAdmin = workspace?.role === "owner" || workspace?.role === "admin";
  const { activeAppId } = useActiveApp();
  const resolvedNavQuery = useResolvedNav(activeAppId ?? undefined);

  const groups = useMemo(
    () => buildNavGroups(entitiesQuery.data, modulesQuery.data),
    [entitiesQuery.data, modulesQuery.data],
  );

  // Domain-module links are gated strictly by installed solutions: a module only
  // appears when a solution that provides it is installed. Nothing installed → no
  // domain modules (you install a package/solution to get them). This is what makes
  // an industry-package workspace (e.g. School) show only its own screens, not the
  // full core-ERP module list.
  const installedSlugs = useMemo(() => {
    const rows = installedQuery.data?.results ?? [];
    return new Set(rows.map((r) => r.solution_slug));
  }, [installedQuery.data]);
  const moduleLinks = useMemo(
    () => MODULE_LINKS.filter((l) => l.solutions.some((s) => installedSlugs.has(s))),
    [installedSlugs],
  );

  // A published Studio navigation (app or workspace scope) overrides the metadata nav for its section.
  const resolved = resolvedNavQuery.data as ResolvedNavigation | Record<string, never> | undefined;
  const customGroups = resolved && "groups" in resolved ? resolved.groups : [];

  const loading = entitiesQuery.isLoading || modulesQuery.isLoading;

  return (
    <nav className="flex flex-col gap-1 p-2" aria-label="Primary">
      {[...PLATFORM_LINKS, ...moduleLinks, ...TOOL_LINKS]
        .filter((l) => isAdmin || !l.adminOnly)
        .map((l) => (
        <NavLink
          key={l.href}
          href={l.href}
          label={t(l.key, l.label)}
          active={l.exact ? pathname === l.href : pathname.startsWith(l.href)}
          icon={l.icon}
        />
      ))}
      <div className="my-2 h-px bg-border" />

      {loading && (
        <div className="space-y-2 p-1">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      )}

      {/* A published custom menu (Studio Navigation) takes over; otherwise the metadata nav shows. */}
      {customGroups.length > 0 ? (
        customGroups.map((group, gi) => (
          <div key={`${group.label}-${gi}`} className="mt-3 first:mt-0">
            <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {group.label}
            </p>
            {group.items.map((item, ii) => {
              const href = navItemHref(item);
              return item.type === "external" ? (
                <a
                  key={`${item.label}-${ii}`}
                  href={href}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <span className="truncate">{item.label}</span>
                </a>
              ) : (
                <span key={`${item.label}-${ii}`} onClick={onNavigate}>
                  <NavLink href={href} label={item.label} active={pathname.startsWith(href)} />
                </span>
              );
            })}
          </div>
        ))
      ) : (
        <>
          {!loading && groups.length === 0 && (
            <EmptyState className="border-0 p-4 text-left" title="No entities yet" />
          )}

          {!loading &&
            groups.map((g) => (
              <div key={g.module?.id ?? "_other"} className="mt-3 first:mt-0">
                <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {g.module?.name ?? "Other"}
                </p>
                {g.entities.map((e) => (
                  <span key={e.id} onClick={onNavigate}>
                    <NavLink
                      href={`/e/${e.slug}`}
                      label={e.plural_name || e.name}
                      active={pathname.startsWith(`/e/${e.slug}`)}
                    />
                  </span>
                ))}
              </div>
            ))}
        </>
      )}
    </nav>
  );
}
