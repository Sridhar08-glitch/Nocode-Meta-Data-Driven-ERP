"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useSearch } from "@/lib/search/hooks";
import { cn } from "@/lib/utils";

interface NavCommand {
  label: string;
  href: string;
  keywords: string;
}
const NAV: NavCommand[] = [
  { label: "Home", href: "/home", keywords: "home dashboard" },
  { label: "Studio", href: "/studio", keywords: "studio builder entity field" },
  { label: "Applications", href: "/studio/applications", keywords: "application app builder studio" },
  { label: "Home layouts", href: "/studio/home-layouts", keywords: "home layout widget studio" },
  { label: "Navigation menus", href: "/studio/navigation", keywords: "navigation menu studio" },
  { label: "Query builder", href: "/query", keywords: "query nql" },
  { label: "Analytics", href: "/analytics", keywords: "analytics kpi key performance indicator scorecard executive ceo cfo coo chro cio metric target threshold erp health registry" },
  { label: "KPI registry", href: "/analytics/kpis", keywords: "analytics kpi registry create nql native aggregate target threshold direction metric" },
  { label: "Executive scorecards", href: "/analytics/scorecards", keywords: "analytics scorecard executive ceo cfo coo chro cio role kpi good warning critical" },
  { label: "ERP health", href: "/analytics/health", keywords: "analytics erp health kpi evaluate category module status grade" },
  { label: "Reports", href: "/reports", keywords: "report" },
  { label: "Dashboards", href: "/dashboards", keywords: "dashboard widget" },
  { label: "Workflows", href: "/workflows", keywords: "workflow automation" },
  { label: "Rules", href: "/rules", keywords: "rules business" },
  { label: "Approvals", href: "/approvals", keywords: "approval" },
  { label: "SLAs", href: "/sla", keywords: "sla" },
  { label: "Business calendars", href: "/calendars", keywords: "calendar business hours holiday" },
  { label: "Notification templates", href: "/templates", keywords: "template notification" },
  { label: "Email templates", href: "/templates/email", keywords: "email template locale render" },
  { label: "Document templates (PDF)", href: "/templates/documents", keywords: "document pdf template render" },
  { label: "Documents", href: "/documents", keywords: "documents files folders upload attachments" },
  { label: "Public forms", href: "/public-forms", keywords: "public forms submissions intake approve reject" },
  { label: "Activity", href: "/activity", keywords: "activity feed" },
  { label: "Permissions", href: "/permissions", keywords: "permission role" },
  { label: "Solutions", href: "/solutions", keywords: "solution template install provision end-to-end catalog erp app" },
  { label: "Create solution", href: "/solutions/new", keywords: "create solution wizard compose provision new build erp blocks" },
  { label: "Process catalog", href: "/catalog", keywords: "catalog process blueprint install marketplace" },
  { label: "Feature flags", href: "/feature-flags", keywords: "feature flag rollout toggle" },
  { label: "Security settings", href: "/settings/security", keywords: "security mfa 2fa two-factor passkey totp" },
  { label: "Developer portal", href: "/developer", keywords: "developer webhook connector oauth api swagger integration" },
  { label: "Admin", href: "/admin", keywords: "admin health tenant settings" },
  { label: "Tenant health", href: "/admin/health", keywords: "health metrics kpi sla latency" },
  { label: "Audit log", href: "/admin/audit", keywords: "audit log history compliance events" },
  { label: "Configuration history", href: "/admin/config-vcs", keywords: "config vcs commit diff rollback version" },
  { label: "Data lineage", href: "/admin/lineage", keywords: "lineage upstream downstream impact graph" },
  { label: "Dependencies & impact", href: "/admin/dependencies", keywords: "dependency impact analysis change safety used by safe delete promotion precheck blast radius graph" },
  { label: "Enterprise certification", href: "/admin/certification", keywords: "certification integration health architecture validation simulation cross module readiness erp report verdict end to end" },
  { label: "Environment promotions", href: "/admin/promotions", keywords: "environment promotion release management dev test uat prod deploy package approve rollback merge promote" },
  { label: "Numbering sequences", href: "/admin/numbering", keywords: "numbering sequence invoice number prefix gapless document" },
  { label: "Accounting", href: "/accounting", keywords: "accounting general ledger gl finance" },
  { label: "Journal entries", href: "/accounting/journal", keywords: "journal entry double-entry debit credit post reverse gl" },
  { label: "Chart of accounts", href: "/accounting/accounts", keywords: "chart accounts coa asset liability equity revenue expense" },
  { label: "Accounting periods", href: "/accounting/periods", keywords: "period fiscal close lock accounting" },
  { label: "Financial reports", href: "/accounting/reports", keywords: "trial balance profit loss income statement balance sheet general ledger financial report" },
  { label: "Inventory", href: "/inventory", keywords: "inventory stock warehouse item sku fifo valuation" },
  { label: "Inventory items", href: "/inventory/items", keywords: "inventory item sku product stock master" },
  { label: "Warehouses", href: "/inventory/warehouses", keywords: "warehouse location inventory stock" },
  { label: "Stock & valuation", href: "/inventory/stock", keywords: "stock balance on hand valuation inventory value cost" },
  { label: "Stock transactions", href: "/inventory/transactions", keywords: "receive issue adjust transfer stock movement inventory" },
  { label: "Stock movements", href: "/inventory/movements", keywords: "stock movement ledger history inventory receipt issue" },
  { label: "Manufacturing", href: "/manufacturing", keywords: "manufacturing mrp production order bom bill of materials work center routing operation oee lot trace quality ncr shop floor make" },
  { label: "BOMs & work centers", href: "/manufacturing/boms", keywords: "manufacturing bom bill of materials work center routing standard cost explode component approve" },
  { label: "Production orders", href: "/manufacturing/orders", keywords: "manufacturing production order mo release issue complete close operation reservation oee wip" },
  { label: "MRP", href: "/manufacturing/mrp", keywords: "manufacturing mrp material requirements planning demand net requirement shortage manufacture purchase" },
  { label: "Manufacturing quality", href: "/manufacturing/quality", keywords: "manufacturing quality check ncr non-conformance lot trace traceability inspection" },
  { label: "Procurement", href: "/procurement", keywords: "procurement vendor supplier rfq purchase order goods receipt vendor bill purchasing buy" },
  { label: "CRM", href: "/crm", keywords: "crm lead account contact opportunity activity pipeline sales qualify win lose deal customer" },
  { label: "HR", href: "/hr", keywords: "hr human resources employee candidate interview offer hire recruit leave attendance performance promotion transfer offboard people org" },
  { label: "Payroll", href: "/payroll", keywords: "payroll salary structure component pay period run payslip wage gross net deduction loan advance overtime adjustment settlement" },
  { label: "Salary structures", href: "/payroll/structures", keywords: "payroll salary structure component earning deduction benefit" },
  { label: "Payroll runs", href: "/payroll/runs", keywords: "payroll run period calculate approve post lock pay period" },
  { label: "Payslips", href: "/payroll/payslips", keywords: "payslip payroll pay net gross deduction" },
  { label: "Payroll loans & inputs", href: "/payroll/loans", keywords: "payroll loan advance overtime adjustment bonus" },
  { label: "Assets", href: "/assets", keywords: "asset eam equipment registry assignment transfer maintenance work order inspection warranty depreciation disposal retire" },
  { label: "Asset depreciation", href: "/assets/depreciation", keywords: "asset depreciation schedule straight line declining balance net book value run period preview" },
  { label: "Asset disposals", href: "/assets/disposals", keywords: "asset disposal sale scrap donation write off gain loss retire" },
  { label: "Projects", href: "/projects", keywords: "project management psa portfolio program task milestone deliverable sprint timesheet expense risk issue change request quality review cost rollup financials evm schedule critical path resource capacity utilization baseline budget" },
  { label: "Project financials", href: "/projects/financials", keywords: "project financials budget profitability earned value evm cpi spi cost variance estimate at completion cost entry rollup" },
  { label: "Project schedule", href: "/projects/schedule", keywords: "project schedule critical path gantt float duration timeline" },
  { label: "Project resources", href: "/projects/resources", keywords: "project resources utilization capacity allocation conflict over allocated hours" },
  { label: "Helpdesk", href: "/helpdesk", keywords: "helpdesk itsm ticket service desk support incident problem change major incident knowledge base csat sla agent field service escalation auto assign" },
  { label: "Helpdesk knowledge", href: "/helpdesk/knowledge", keywords: "helpdesk knowledge base article recommend recommendation category keyword search kb" },
  { label: "Helpdesk SLA dashboard", href: "/helpdesk/sla", keywords: "helpdesk sla dashboard breached warning on track met paused service level" },
  { label: "Backups & restore", href: "/admin/backups", keywords: "backup restore pitr point in time" },
  { label: "Marketplace", href: "/admin/marketplace", keywords: "marketplace plugin install store" },
  { label: "Recycle bin", href: "/admin/recycle-bin", keywords: "recycle bin trash deleted restore purge" },
  { label: "External portal", href: "/admin/portal", keywords: "portal external customer partner users grants" },
  { label: "Branding", href: "/admin/branding", keywords: "branding white-label theme smtp" },
  { label: "Localization", href: "/admin/localization", keywords: "localization locale timezone currency translation" },
  { label: "Import data", href: "/import", keywords: "import csv upload" },
  { label: "Search", href: "/search", keywords: "search" },
];

/** Global Cmd/Ctrl+K command palette: fuzzy nav + live record search (Phase F2.6). */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(q), 200);
    return () => clearTimeout(id);
  }, [q]);

  const search = useSearch(debounced, { limit: 8 });
  const navMatches = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return NAV;
    return NAV.filter((n) => (n.label + " " + n.keywords).toLowerCase().includes(needle));
  }, [q]);

  function go(href: string) {
    setOpen(false);
    setQ("");
    router.push(href);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setQ("");
      }}
    >
      <DialogContent className="top-[20%] translate-y-0 p-0">
        <DialogHeader className="sr-only">
          <DialogTitle>Command palette</DialogTitle>
        </DialogHeader>
        <Input
          aria-label="Command palette search"
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search records or jump to…"
          className="border-0 border-b border-border focus-visible:ring-0"
        />
        <div className="max-h-80 overflow-y-auto p-2">
          {search.data && search.data.results.length > 0 && (
            <Section title="Records">
              {search.data.results.map((r) => (
                <Item key={`${r.entity_slug}/${r.record_id}`} onClick={() => go(`/e/${r.entity_slug}/${r.record_id}`)}>
                  <span className="truncate">{r.title || r.record_id}</span>
                  <span className="ml-auto text-xs text-muted-foreground">{r.entity_slug}</span>
                </Item>
              ))}
            </Section>
          )}
          {navMatches.length > 0 && (
            <Section title="Go to">
              {navMatches.map((n) => (
                <Item key={n.href} onClick={() => go(n.href)}>
                  {n.label}
                </Item>
              ))}
            </Section>
          )}
          {navMatches.length === 0 && (!search.data || search.data.results.length === 0) && (
            <p className="px-2 py-6 text-center text-sm text-muted-foreground">No matches.</p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-2">
      <p className="px-2 py-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
      <ul>{children}</ul>
    </div>
  );
}
function Item({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <li>
      <button onClick={onClick} className={cn("flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted")}>
        {children}
      </button>
    </li>
  );
}
