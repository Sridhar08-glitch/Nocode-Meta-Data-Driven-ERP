"use client";

import { Connectors } from "@/components/developer/connectors";
import { InboundWebhooks } from "@/components/developer/inbound-webhooks";
import { OAuthApps } from "@/components/developer/oauth-apps";
import { WebhookBuilder } from "@/components/developer/webhook-builder";
import { Button } from "@/components/ui/button";

const SWAGGER_URL = `${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/openapi/swagger/`;

export default function DeveloperPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Developer portal</h1>
        <p className="text-sm text-muted-foreground">
          Webhooks, HTTP connectors, OAuth apps, and the live API reference.
        </p>
      </div>

      <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
        <div>
          <h2 className="text-sm font-medium">API reference</h2>
          <p className="text-xs text-muted-foreground">Interactive OpenAPI (Swagger) documentation for every endpoint.</p>
        </div>
        <Button asChild variant="outline">
          <a href={SWAGGER_URL} target="_blank" rel="noreferrer">
            Open Swagger
          </a>
        </Button>
      </section>

      <WebhookBuilder />
      <InboundWebhooks />
      <Connectors />
      <OAuthApps />

      <p className="border-t pt-4 text-xs text-muted-foreground">
        API key management (create / scope / rotate / revoke) is not yet exposed by the backend API —
        it will land when those endpoints exist.
      </p>
    </div>
  );
}
