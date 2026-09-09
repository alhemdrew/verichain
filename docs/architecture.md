# VeriChain Architecture

VeriChain keeps evidence as immutable digital records with a documented chain of custody and cryptographic verification flow.

## Components

- API: FastAPI backend that owns evidence lifecycle, auth, verification, and reporting logic.
- Web client: Vite + React interface for investigators to manage cases and evidence.
- Desktop shell: Tauri scaffold for local desktop packaging.
- Shared packages: cross-platform type contracts and UI primitives.

## Trust model

- Evidence bytes are preserved at the source and never mutated in place.
- SHA-256 hashes and manifests verify the canonical state.
- Signing and custody events are recorded as part of the evidence lifecycle.
- Local storage and generated runtime files remain workspace-local and excluded from Git.
