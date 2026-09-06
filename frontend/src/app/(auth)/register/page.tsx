"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Field } from "@/components/auth/field";
import { PasswordStrengthMeter } from "@/components/auth/password-strength-meter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { authApi } from "@/lib/auth/api";
import { ApiError } from "@/lib/api/errors";

const schema = z.object({
  full_name: z.string().min(1, "Your name is required"),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(10, "Use at least 10 characters"),
});
type Values = z.infer<typeof schema>;

export default function RegisterPage() {
  const [sent, setSent] = useState(false);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: "", email: "", password: "" },
  });
  const password = form.watch("password");

  async function onSubmit(values: Values) {
    try {
      await authApi.register(values);
      setSent(true);
    } catch (err) {
      if (err instanceof ApiError) {
        for (const [field, msgs] of Object.entries(err.fieldErrors)) {
          form.setError(field as keyof Values, { message: msgs[0] });
        }
        if (!Object.keys(err.fieldErrors).length) toast.error(err.message);
      } else {
        toast.error("Registration failed");
      }
    }
  }

  if (sent) {
    return (
      <div className="space-y-2 text-center">
        <h1 className="text-xl font-semibold">Check your email</h1>
        <p className="text-sm text-muted-foreground">
          We sent a verification link to <strong>{form.getValues("email")}</strong>. Open it to
          activate your account.
        </p>
        <Link href="/login" className="text-sm text-primary hover:underline">
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-1 text-center">
        <h1 className="text-xl font-semibold">Create your account</h1>
      </div>
      <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <Field label="Full name" htmlFor="full_name" error={form.formState.errors.full_name?.message}>
          <Input id="full_name" autoComplete="name" {...form.register("full_name")} />
        </Field>
        <Field label="Email" htmlFor="email" error={form.formState.errors.email?.message}>
          <Input id="email" type="email" autoComplete="email" {...form.register("email")} />
        </Field>
        <Field label="Password" htmlFor="password" error={form.formState.errors.password?.message}>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            {...form.register("password")}
          />
          <PasswordStrengthMeter password={password} />
        </Field>
        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Creating…" : "Create account"}
        </Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </>
  );
}
