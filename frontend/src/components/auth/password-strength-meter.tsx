"use client";

import { scorePassword } from "@/lib/auth/password-strength";
import { cn } from "@/lib/utils";

const BAR_COLORS = [
  "bg-destructive",
  "bg-destructive",
  "bg-warning",
  "bg-success",
  "bg-success",
];

export function PasswordStrengthMeter({ password }: { password: string }) {
  const { score, label, suggestions } = scorePassword(password);
  if (!password) return null;
  return (
    <div className="space-y-1" aria-live="polite">
      <div className="flex gap-1" aria-hidden>
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={cn(
              "h-1 flex-1 rounded-full",
              i < score ? BAR_COLORS[score] : "bg-muted",
            )}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        Strength: <span className="font-medium text-foreground">{label}</span>
        {suggestions[0] && <span> · {suggestions[0]}</span>}
      </p>
    </div>
  );
}
