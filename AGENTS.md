# Repository instructions for coding agents

This file is an engineering contract for changes to Colloquily. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/ENGINEERING_STANDARDS.md](docs/ENGINEERING_STANDARDS.md), and [CONTRIBUTING.md](CONTRIBUTING.md) before a nontrivial change. More specific instructions live in `backend/AGENTS.md`, `frontend/AGENTS.md`, and `src-tauri/AGENTS.md`.

## Product and system boundaries

- Colloquily is a **single-user, local-first oral-exam study app**, not a hosted multi-tenant service.
- Preserve local inference and storage. No cloud LLM fallback, telemetry, remote document upload, or new network integration without explicit approval and an updated privacy/security review.
- Keep exam data, source evidence, retrieval indexes, question history, and progress scoped to the active exam. Do not expose another exam's records by accident.
- Generated questions and assessments must be grounded in **accepted, current** source evidence. Do not bypass validation, invent citations, auto-accept uncertain content, or add generic fallback questions to disguise model failure.
- Existing users' SQLite data, migration paths, backups, and review history must survive upgrades. Do not destructively reset or rewrite a workspace to pass a test.
- The HTTP listener must remain loopback-only; preserve desktop launch-token, host/origin and file-path protections.

## Working method

1. Inspect the owning module, its callers, relevant tests, and applicable nested `AGENTS.md`.
2. Describe the behavior or invariant being changed, identify failure paths, and make the smallest coherent patch.
3. Keep HTTP contracts in `backend/models/api.py`, `backend/api/routes.py`, `frontend/src/types/index.ts`, and `frontend/src/api/client.ts` aligned as needed.
4. Add a regression test for bug fixes and for state transitions, data migrations, retrieval, model-validation, and security changes.
5. Update user-facing docs, translations (English and German), architecture notes, and ADRs when changing behavior or design.
6. Report commands run, their outcomes, and checks that could not run. Do not claim CI, inference, installer, or platform verification without evidence.

## Standard checks

With Python 3.11 environment active and Node.js 22+ installed:

```bash
npm ci
npm test
npm run test:api
python scripts/test_core.py
npm run build
cargo check --locked --manifest-path src-tauri/Cargo.toml
```

Rust checking needs the Tauri platform prerequisites; local-model acceptance requires separately installed models. Run appropriate focused tests first; use CI as an additional signal, not as a substitute for local reasoning.

## Changes requiring special care

- Database schema or storage paths: add migration, rollback/backup discussion, and persistence regressions.
- Question/evidence logic: test missing/stale/rejected evidence, duplicate behavior, and failure-to-generate cases.
- Desktop runtime/build: test process start/stop, origin/token protection, and target-native packaging where possible.
- Dependencies or installer contents: review licensing, offline/privacy effects, frozen packaging, and lockfiles.
- Never commit personal documents, local databases, model weights, cached indexes, log files, secrets, or signing material.

## Review criteria

Flag regressions in privacy, source grounding, exam isolation, persistence, process lifecycle, and accessibility before style issues. Favor readable changes and clear explanations over unnecessary abstraction or sweeping rewrites.
