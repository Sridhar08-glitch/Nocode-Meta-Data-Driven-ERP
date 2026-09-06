"use client";

import { LocalizationSettings } from "@/components/admin/localization-settings";

export default function AdminLocalizationPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Localization</h1>
        <p className="text-sm text-muted-foreground">
          Default locale, timezone, and currency for the workspace, plus per-entity label
          translations.
        </p>
      </div>
      <LocalizationSettings />
    </div>
  );
}
