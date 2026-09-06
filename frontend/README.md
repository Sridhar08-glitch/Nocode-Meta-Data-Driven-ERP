# Sridhar ERP — Frontend

The Next.js 14 (App Router, TypeScript) frontend for **Sridhar ERP** — a single generic, metadata-driven runtime. Entities defined in the Studio render automatically through the shared form renderer, record runtime, and view engine; there is no per-entity React code.

**Author / Developer: Sridhar**

## Highlights

- **Generic record runtime** — list / detail / create / edit for any entity, driven entirely by backend metadata (`/e/[entity]`).
- **THE Form Renderer** — one React Hook Form + Zod renderer for every field type, section layout, wizard, and conditional rule.
- **View engine** — Kanban, Calendar, Tree, Org Chart, Timeline, Map, Chart (20 chart types), Dashboard, Pivot, and Gantt over one shared data model.
- **Studio builders** — entities, fields, forms, permissions, workflows, rules, approvals, SLA, navigation, home layouts, applications.
- **Realtime** — WebSocket notification center, live record/workflow/dashboard streams, presence.
- **Command palette** (Cmd+K), global search, import/export wizard, i18n with RTL, offline outbox + PWA manifest.
- **Separate portal realm** — external portal login and scoped data views, fully isolated from member auth.

## Getting started

```bash
npm install
npm run dev          # http://localhost:3000  (expects the Django API on :8000)
```

Set `NEXT_PUBLIC_API_URL` to the backend URL (defaults target `http://localhost:8000`).

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | development server |
| `npm run build` | production build |
| `npm run test` | vitest suite |
| `npm run test:cov` | tests with coverage |
| `npm run typecheck` | TypeScript check |
| `npm run lint` | ESLint |
| `npm run e2e` | Playwright end-to-end tests |
| `npm run gen:api` | regenerate the typed API client from `openapi.yaml` |

## Documentation

See `../PROJECT_HANDBOOK.md` for the full platform architecture and `../PHASE_F*_REPORT.md` for the frontend build history.
