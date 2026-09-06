"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { authApi } from "@/lib/auth/api";
import { applyTokenResponse } from "@/lib/auth/session";

function VerifyInner() {
  const router = useRouter();
  const token = useSearchParams().get("token");
  const [status, setStatus] = useState<"verifying" | "ok" | "error">("verifying");
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return; // verify exactly once (token is single-use)
    ran.current = true;
    if (!token) {
      setStatus("error");
      return;
    }
    authApi
      .verifyEmail(token)
      .then((res) => {
        applyTokenResponse(res);
        setStatus("ok");
        router.replace("/home");
      })
      .catch(() => setStatus("error"));
  }, [token, router]);

  if (status === "verifying") {
    return (
      <div className="flex flex-col items-center gap-3 text-center">
        <Spinner />
        <p className="text-sm text-muted-foreground">Verifying your email…</p>
      </div>
    );
  }
  if (status === "ok") {
    return <p className="text-center text-sm text-muted-foreground">Verified! Redirecting…</p>;
  }
  return (
    <div className="space-y-3 text-center">
      <h1 className="text-xl font-semibold">Verification failed</h1>
      <p className="text-sm text-muted-foreground">
        This link is invalid or has expired. Try signing in to request a new one.
      </p>
      <Button asChild className="w-full">
        <Link href="/login">Go to sign in</Link>
      </Button>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyInner />
    </Suspense>
  );
}
