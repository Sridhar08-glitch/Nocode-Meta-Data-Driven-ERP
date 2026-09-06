import { AppShell } from "@/components/shell/app-shell";
import { TenantProvider } from "@/lib/tenant/context";

/** Authenticated shell: tenant context (workspaces/branding/flags) + metadata-driven
 *  sidebar + topbar. Route protection is enforced by `middleware.ts` + the API
 *  401→logout interceptor. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <TenantProvider>
      <AppShell>{children}</AppShell>
    </TenantProvider>
  );
}
