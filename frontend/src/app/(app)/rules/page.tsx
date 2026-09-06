"use client";

import { RuleBuilder } from "@/components/rules/rule-builder";

export default function RulesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Business rules</h1>
        <p className="text-sm text-muted-foreground">
          NQL conditions that set fields or block saves when a record changes.
        </p>
      </div>
      <RuleBuilder />
    </div>
  );
}
