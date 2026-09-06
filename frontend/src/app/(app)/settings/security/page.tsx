"use client";

import { AccountCredentials } from "@/components/settings/account-credentials";
import { SecuritySettings } from "@/components/settings/security-settings";

export default function SecuritySettingsPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Security</h1>
        <p className="text-sm text-muted-foreground">
          Password, email, two-factor authentication, passkeys, and account protection.
        </p>
      </div>
      <AccountCredentials />
      <SecuritySettings />
    </div>
  );
}
