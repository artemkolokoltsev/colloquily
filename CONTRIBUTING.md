# Contributing to Colloquily

Colloquily is a local-first open-source application for oral-exam preparation. Contributions are welcome, especially regression tests, reliability improvements, accessible UI changes and documentation fixes.

## Before changing code

Read [architecture](docs/ARCHITECTURE.md), [engineering standards](docs/ENGINEERING_STANDARDS.md), and [repository instructions](AGENTS.md). Coding agents should also follow scoped instructions in the directory being changed.

For most contributions: open a focused issue or pull request, explain the expected behavior, and preserve established data, privacy and source-grounding contracts. Prefer one purpose per PR; unrelated formatting churn makes high-risk changes harder to review.

## Set up and test

Use Python 3.11 and Node.js 22+; Rust and platform prerequisites are required for native desktop work. See [README development setup](README.md#development).

```bash
npm ci
npm test
npm run test:api
python scripts/test_core.py
npm run build
```

For desktop changes, also run `cargo check --locked --manifest-path src-tauri/Cargo.toml`. For frozen backend and installer changes, consult [desktop verification](docs/desktop.md). Tests use disposable/synthetic data; do not publish real exam documents or local workspaces.

## Pull request expectations

Explain the problem, behavior changed, affected architecture layers, test evidence (with actual outcomes), and any remaining risks. Include screenshots for material UI changes. In particular:

- API changes: update Pydantic models and frontend types/callers together.
- Evidence/model changes: add tests for invalid output, stale support, rejection and retry paths.
- Storage changes: explain migration and backward compatibility, test on synthetic workspaces.
- UX changes: update English/German translations and keyboard/accessibility behavior.
- Privacy, external network or dependency changes: update security/licensing documentation and obtain project-owner review.
- Architecture changes: add an ADR under `docs/adr/`.

## Reporting bugs responsibly

Describe reproduction steps, OS/application version, expected and actual behavior, and sanitized logs if needed. **Never attach source course PDFs, private study answers, database files, API tokens or model credentials.** If a report could expose a security issue, avoid publishing exploit details or sensitive data in a public issue.

## Review standard

The objective is a small, understandable, tested change that leaves users' existing local workspaces intact. An agent-generated patch receives the same scrutiny as a human-authored one. See [engineering standards](docs/ENGINEERING_STANDARDS.md) for required invariants and the verification ladder.
