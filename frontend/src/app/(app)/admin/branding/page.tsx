"use client";

import { BrandingSettings } from "@/components/admin/branding-settings";

export default function AdminBrandingPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Branding</h1>
        <p className="text-sm text-muted-foreground">
          White-label the workspace — app name, logo, theme colors, custom CSS, and outgoing email.
        </p>
      </div>
      <BrandingSettings />
    </div>
  );
}
