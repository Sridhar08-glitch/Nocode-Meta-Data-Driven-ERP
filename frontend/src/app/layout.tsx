import type { Metadata } from "next";

import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sridhar ERP",
  description: "Metadata-driven, event-sourced, no-code ERP platform.",
  applicationName: "Sridhar ERP",
  authors: [{ name: "Sridhar" }],
  creator: "Sridhar",
  publisher: "Sridhar",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
