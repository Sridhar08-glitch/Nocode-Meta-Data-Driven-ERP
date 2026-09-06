"use client";

import { useTheme } from "next-themes";
import { Toaster as Sonner, toast } from "sonner";

/** App toaster (sonner). Mounted once in the root providers; call `toast()` anywhere. */
export function Toaster() {
  const { resolvedTheme } = useTheme();
  return (
    <Sonner
      theme={(resolvedTheme as "light" | "dark" | undefined) ?? "system"}
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast:
            "group rounded-md border border-border bg-popover text-popover-foreground shadow-md",
          description: "text-muted-foreground",
          actionButton: "bg-primary text-primary-foreground",
        },
      }}
    />
  );
}

export { toast };
