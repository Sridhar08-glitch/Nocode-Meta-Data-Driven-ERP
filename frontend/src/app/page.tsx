import { API_BASE_URL } from "@/lib/api/client";

/** F0 landing — confirms the shell boots + theme tokens render. Replaced by the
 *  authenticated app shell in F1.4. */
export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center gap-6 px-6 text-center">
      <span className="rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
        Sridhar ERP · Frontend F0
      </span>
      <h1 className="text-4xl font-bold tracking-tight">No-code ERP platform</h1>
      <p className="text-muted-foreground">
        Scaffold online. Typed API client wired to{" "}
        <code className="rounded bg-muted px-1.5 py-0.5 text-foreground">{API_BASE_URL}</code>.
      </p>
      <div className="flex gap-3">
        <span className="rounded-md border border-border px-4 py-2 text-sm">Strict TS</span>
        <span className="rounded-md border border-border px-4 py-2 text-sm">Tailwind theme</span>
        <span className="rounded-md border border-border px-4 py-2 text-sm">gen:api</span>
      </div>
    </main>
  );
}
