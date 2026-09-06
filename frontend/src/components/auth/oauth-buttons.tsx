"use client";

import { Button } from "@/components/ui/button";
import { oauthAuthorizeUrl } from "@/lib/auth/api";

/** Google + Microsoft sign-in. Full-page redirect to the backend authorize endpoint,
 *  which (after consent) redirects to /oauth/callback#access=…&refresh=…. */
export function OAuthButtons() {
  return (
    <div className="grid grid-cols-2 gap-3">
      <Button
        type="button"
        variant="outline"
        onClick={() => window.location.assign(oauthAuthorizeUrl.google)}
      >
        Google
      </Button>
      <Button
        type="button"
        variant="outline"
        onClick={() => window.location.assign(oauthAuthorizeUrl.microsoft)}
      >
        Microsoft
      </Button>
    </div>
  );
}
