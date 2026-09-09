# VeriChain Implementation Plan (Phase 1)

This document describes the concrete implementation phases and dependencies for the VeriChain prototype, and the exact scope for Phase 1 (project foundation).

## Goals

- Establish monorepo structure.
- Provide runnable FastAPI backend foundation.
- Provide React + TypeScript frontend skeleton (Vite).
- Provide Tauri desktop scaffold and Rust placeholder.
- Provide Docker Compose for Postgres + backend.
- Provide shared TypeScript types and UI package.
- Provide environment-based configuration examples.
- Provide authentication foundation (stubs) and placeholder UI routes.

## High-level phases

1. Project foundation (this phase)
   - Monorepo scaffold
   - FastAPI backend foundation
   - Docker Compose (Postgres + backend)
   - React frontend skeleton + routing
   - Tauri desktop scaffold (placeholder)
   - Shared types and UI package
   - Env examples and config
   - Basic auth stubs and placeholder pages
   - Basic tests and health checks

2. Authentication
3. Case management CRUD
4. Evidence model & hashing
5. Evidence collection UI/engine
6. Local protected vault
7. Custody chain
8. Sync engine and server verification
9. Sharing & derivatives
10. Reporting & final polish

## Dependencies (Phase 1)

- Python 3.10+ (FastAPI + uvicorn)
- Node 18+ (Vite + React + TypeScript)
- Rust & Cargo (for Tauri later; scaffold provided)
- Docker & Docker Compose (for Postgres + optional backend container)

## Phase 1 Deliverables

- `apps/api/` - FastAPI app with health and auth stub endpoints
- `apps/web/` - Vite React TypeScript app with routes and dark design system
- `apps/desktop/` - Tauri scaffold placeholder and `src-tauri` layout
- `packages/types/` - shared TypeScript interfaces
- `packages/ui/` - basic design system (CSS variables, theme)
- `docker/docker-compose.yml` - Postgres + api service (dev)
- `.env.example` - environment variables examples
- `IMPLEMENTATION_PLAN.md` - this file

## Phase 1 Success Criteria

- Backend starts: `uvicorn apps.api.main:app --reload --port 8000` and returns a healthy response at `/health`.
- Frontend dev server can be started (instructions provided) and shows the placeholder pages and navigation.
- Docker Compose brings up Postgres for development.
- Shared types are available for frontend packages.

---

When Phase 1 is complete, I will stop and ask for your permission to continue to Phase 2 (Authentication).
