import type { MetadataRoute } from "next";

/**
 * Web app manifest (Phase F2.9) — makes Sridhar ERP installable as a PWA (the first concrete step of
 * the mobile/offline acceptance track). Full offline form sync (service worker + queued mutations)
 * is a dedicated follow-up; see PHASE_F2_9_REPORT.md.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Sridhar ERP",
    short_name: "Sridhar",
    description: "Sridhar ERP — metadata-driven, no-code ERP platform.",
    start_url: "/home",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#2563eb",
    icons: [
      {
        src: "/favicon.ico",
        sizes: "any",
        type: "image/x-icon",
      },
    ],
  };
}
