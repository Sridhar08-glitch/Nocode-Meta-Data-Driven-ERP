"use client";

import { DocumentBrowser } from "@/components/documents/document-browser";

export default function DocumentsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Documents</h1>
        <p className="text-sm text-muted-foreground">
          Upload, organize in folders, version, and download files (signed, expiring links).
        </p>
      </div>
      <DocumentBrowser />
    </div>
  );
}
