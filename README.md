# VeriChain

VeriChain is a digital-evidence integrity platform designed to preserve evidence, track custody, verify cryptographic state, and generate reviewable reports for investigations.

## Repository layout

- `apps/api` — FastAPI backend and evidence integrity services
- `apps/web` — React + Vite client
- `apps/desktop` — Tauri desktop shell scaffold
- `packages/types` and `packages/ui` — shared platform contracts and UI primitives
- `docker/` — local Docker Compose setup
- `docs/` — architecture, threat model, crypto model, evidence life cycle, and API references

## Getting started

1. Copy the example environment file and adjust values locally:

```bash
cp .env.example .env
```

2. Start the backend and local dependencies:

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

3. Start the frontend:

```bash
cd apps/web
npm install
npm run dev
```

## Security note

This repository intentionally keeps local secrets, private keys, runtime databases, and evidence vault material out of Git. Use local config files and generated runtime directories only; never commit `.env`, certificate material, signing keys, SQLite databases, or evidence payloads.

## Project docs

- `IMPLEMENTATION_PLAN.md`
- `docs/architecture.md`
- `docs/threat-model.md`
- `docs/crypto-model.md`
- `docs/evidence-lifecycle.md`
- `docs/api.md`

## Local validation

Before opening a PR or pushing to GitHub, run:

```bash
cd apps/api
pytest -q

cd ../web
npm install
npm run build
npx tsc --noEmit
```
