"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { applyOAuthTokens } from "@/lib/auth/session";

/** Lands here after Google/Microsoft consent: backend redirects with
 *  `#access=…&refresh=…`. We consume the hash, store tokens, and enter the app. */
export default function OAuthCallbackPage() {
  const router = useRouter();
  const [failed, setFailed] = useState(false);
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const access = params.get("access");
    const refresh = params.get("refresh");
    // Scrub tokens from the URL immediately.
    window.history.replaceState(null, "", window.location.pathname);
    if (access && refresh && applyOAuthTokens(access, refresh)) {
      router.replace("/home");
    } else {
      setFailed(true);
    }
  }, [router]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 px-4 text-center">
      {failed ? (
        <>
          <h1 className="text-xl font-semibold">Sign-in failed</h1>
          <p className="text-sm text-muted-foreground">We couldn&apos;t complete the sign-in.</p>
          <Button asChild>
            <Link href="/login">Back to sign in</Link>
          </Button>
        </>
      ) : (
        <>
          <Spinner />
          <p className="text-sm text-muted-foreground">Completing sign-in…</p>
        </>
      )}
    </div>
  );
}
