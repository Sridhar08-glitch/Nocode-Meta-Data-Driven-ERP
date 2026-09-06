/*
 * NexusERP service worker (Phase F3.8) — minimal, makes the app installable as a PWA.
 *
 * Deliberately a pass-through: it never caches authenticated navigations or API mutations (auth +
 * tenant scoping make naive caching unsafe). A Workbox precache for static assets + an offline
 * app-shell fallback is the documented follow-up; offline *writes* are handled at the app layer by
 * lib/offline (the outbox), not here.
 */
self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", () => {
  // Pass-through. A fetch handler is required for installability on some browsers.
});
