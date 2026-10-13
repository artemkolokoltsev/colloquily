# Public repository preparation

Reviewed on 2026-09-22. README and application/UI changes are deferred until the next polishing pass.

## Credential findings

- An unused local tracing configuration was preserved at `data/preserved-config/.env.langtrace`. It is ignored, not tracked, and must not be included in a source ZIP or force-added.
- Pattern scans of 210 tracked/untracked candidate paths and 387 unique historical blobs across 8 reachable commits found no recognizable private provider API tokens or private keys. Five local secret values were also checked verbatim against publishable files and historical blobs: no matches.
- Historical `.env.langtrace.example` includes sample/default credential assignments, including a nonempty PostgreSQL password. Its provenance was not verified; if that sample password was ever used for a real service, replace that service password before publishing history. Historical Docker connection strings use environment interpolation.
- Follow-up: removed the login/account-management flow and fixed password defaults. The desktop API reuses the local owner; new identities have a random unused password. RAG controls are available under Advanced settings. Historical commits still contain the old defaults.
- This was a local pattern and exact-value scan, not a guarantee that no unknown credential format exists. Remote-only branches, GitHub settings, external application data, and release artifacts were not inspected.

## Keep local

The updated `.gitignore` excludes these without deleting them:

- `.env` and `.env.*` (sanitized `.env.example` / `.env.*.example` remain eligible for Git).
- `data/`, databases and their WAL/journal/SHM sidecars: uploaded documents, indexes, users, study progress, and runtime settings.
- `.venv/`, `node_modules/`, `build/`, `src-tauri/target/`, `frontend/dist/`, generated sidecar binaries, caches, logs, and `output/` / `.playwright-cli/` captures.
- `data/preserved-source-notes/`: personal course/question material and working UI notes moved out of the source tree; review suitability and redistribution rights before intentionally including examples.
- Common private-key/certificate containers (`*.key`, `*.pem`, `*.p12`, `*.pfx`, `*.keystore`).

Ignored build/cache directories may be removed to reclaim space, but deletion is unnecessary for GitHub. Back up runtime data before deleting anything. At review time, `src-tauri/target/` occupied about 2.3 GB and `build/` about 1.3 GB.

## Keep in the repository

Keep source, tests, synthetic test fixtures, desktop icons, `.github/workflows/desktop.yml`, `package-lock.json`, and `src-tauri/Cargo.lock`.

## Before the final push

1. Finish UI/app polishing and update README from the owner's notes.
2. Choose a license before adding a LICENSE file; no license choice was made in this audit.
3. Review the staged diff, including new files, and repeat the credential scan after final edits.
4. Review Git author names/emails if publishing existing history; that identity metadata is public with commits.
5. Verify installers and release archives separately: `.gitignore` does not filter packaging tools or arbitrary ZIP creation.

Validation: 23 ignore/keep cases passed; no tracked files matched ignore rules; `git diff --check` passed. Personal data and Git history were preserved. Obsolete source files were subsequently removed in the desktop cleanup.
