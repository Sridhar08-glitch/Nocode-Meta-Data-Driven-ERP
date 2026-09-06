"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Field } from "@/components/auth/field";
import { PasswordStrengthMeter } from "@/components/auth/password-strength-meter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { authApi } from "@/lib/auth/api";
import { ApiError } from "@/lib/api/errors";

const schema = z.object({ password: z.string().min(10, "Use at least 10 characters") });
type Values = z.infer<typeof schema>;

function ResetForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { password: "" } });
  const password = form.watch("password");

  async function onSubmit(values: Values) {
    if (!token) {
      toast.error("This reset link is missing its token.");
      return;
    }
    try {
      await authApi.passwordResetConfirm({ token, password: values.password });
      toast.success("Password reset. Please sign in.");
      router.replace("/login");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Reset failed");
    }
  }

  return (
    <>
      <div className="space-y-1 text-center">
        <h1 className="text-xl font-semibold">Choose a new password</h1>
      </div>
      <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <Field label="New password" htmlFor="password" error={form.formState.errors.password?.message}>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            {...form.register("password")}
          />
          <PasswordStrengthMeter password={password} />
        </Field>
        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          Reset password
        </Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        <Link href="/login" className="text-primary hover:underline">
          Back to sign in
        </Link>
      </p>
    </>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetForm />
    </Suspense>
  );
}
