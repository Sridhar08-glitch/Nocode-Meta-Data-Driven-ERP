import { AlertTriangle, Inbox, ShieldX } from "lucide-react";

import { cn } from "@/lib/utils";

import { Button } from "./button";

interface StateProps {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: { label: string; onClick: () => void };
  className?: string;
}

function StateShell({ title, description, icon, action, className }: StateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border p-10 text-center",
        className,
      )}
    >
      {icon}
      <div className="space-y-1">
        <p className="font-medium text-foreground">{title}</p>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {action && (
        <Button variant="outline" size="sm" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}

/** Empty state — no data yet. */
export function EmptyState(props: Omit<StateProps, "icon">) {
  return <StateShell {...props} icon={<Inbox className="size-8 text-muted-foreground" />} />;
}

/** Error state — a request failed; offers a retry action. */
export function ErrorState(props: Omit<StateProps, "icon">) {
  return <StateShell {...props} icon={<AlertTriangle className="size-8 text-destructive" />} />;
}

/** Permission-denied state — the caller lacks access (RBAC/ABAC). */
export function PermissionDeniedState(props: Omit<StateProps, "icon" | "title"> & { title?: string }) {
  return (
    <StateShell
      {...props}
      title={props.title ?? "You don't have access"}
      icon={<ShieldX className="size-8 text-muted-foreground" />}
    />
  );
}
