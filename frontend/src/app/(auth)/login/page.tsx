"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Field } from "@/components/auth/field";
import { OAuthButtons } from "@/components/auth/oauth-buttons";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { authApi, type MfaChallenge, type TokenResponse } from "@/lib/auth/api";
import { applyTokenResponse } from "@/lib/auth/session";
import { ApiError } from "@/lib/api/errors";
import { authenticateWithPasskey, isPasskeySupported } from "@/lib/webauthn/client";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});
type Values = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const [challenge, setChallenge] = useState<MfaChallenge | null>(null);

  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });

  function land(res: TokenResponse) {
    applyTokenResponse(res);
    router.replace("/home");
  }

  async function onSubmit(values: Values) {
    try {
      const res = await authApi.login(values);
      if ("mfa_required" in res) setChallenge(res);
      else land(res);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Login failed");
    }
  }

  if (challenge) {
    return <MfaStep challenge={challenge} onSuccess={land} onBack={() => setChallenge(null)} />;
  }

  return (
    <>
      <div className="space-y-1 text-center">
        <h1 className="text-xl font-semibold">Sign in</h1>
        <p className="text-sm text-muted-foreground">Welcome back to Sridhar ERP</p>
      </div>
      <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <Field label="Email" htmlFor="email" error={form.formState.errors.email?.message}>
          <Input id="email" type="email" autoComplete="email" {...form.register("email")} />
        </Field>
        <Field label="Password" htmlFor="password" error={form.formState.errors.password?.message}>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            {...form.register("password")}
          />
        </Field>
        <div className="text-right">
          <Link href="/forgot-password" className="text-xs text-primary hover:underline">
            Forgot password?
          </Link>
        </div>
        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>
      <div className="relative text-center text-xs text-muted-foreground">
        <span className="bg-card px-2">or continue with</span>
      </div>
      <OAuthButtons />
      <p className="text-center text-sm text-muted-foreground">
        No account?{" "}
        <Link href="/register" className="text-primary hover:underline">
          Create one
        </Link>
      </p>
    </>
  );
}

function MfaStep({
  challenge,
  onSuccess,
  onBack,
}: {
  challenge: MfaChallenge;
  onSuccess: (res: TokenResponse) => void;
  onBack: () => void;
}) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  async function verifyTotp() {
    setBusy(true);
    try {
      onSuccess(await authApi.loginMfa({ mfa_token: challenge.mfa_token, code }));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Invalid code");
    } finally {
      setBusy(false);
    }
  }

  async function verifyPasskey() {
    setBusy(true);
    try {
      const { publicKey } = await authApi.passkeyAuthBegin(challenge.mfa_token);
      const credential = await authenticateWithPasskey(publicKey);
      onSuccess(await authApi.passkeyAuthComplete({ mfa_token: challenge.mfa_token, credential }));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Passkey sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="space-y-1 text-center">
        <h1 className="text-xl font-semibold">Two-factor authentication</h1>
        <p className="text-sm text-muted-foreground">Enter the 6-digit code from your authenticator.</p>
      </div>
      <div className="space-y-4">
        <Field label="Authentication code" htmlFor="code">
          <Input
            id="code"
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="123456"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </Field>
        <Button className="w-full" onClick={verifyTotp} disabled={busy || code.length < 6}>
          Verify
        </Button>
        {isPasskeySupported() && (
          <Button variant="outline" className="w-full" onClick={verifyPasskey} disabled={busy}>
            Use a passkey instead
          </Button>
        )}
        <Button variant="ghost" className="w-full" onClick={onBack} disabled={busy}>
          Back
        </Button>
      </div>
    </>
  );
}
