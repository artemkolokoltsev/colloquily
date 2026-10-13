# v0.1.0 release status

## Implemented and locally tested

- React/Tauri/FastAPI desktop lifecycle, single instance, random loopback port/token, readiness and shutdown handling.
- Empty first workspace, exam isolation, accepted-evidence retrieval, guarded question generation, practice persistence, and extractive fallbacks requiring review.
- German/English detection, persistence, live switching, typed catalogs, and translation-key parity test for the release shell/settings/error path.
- Schema version 10, pre-migration SQLite backups, integrity validation, newer-schema refusal, whole-workspace export/restore validation, source removal/index invalidation.
- Official Tauri v2 updater client, startup/manual checks, approval/progress/restart UI, signed-artifact configuration, native release matrix, and draft GitHub Releases.
- Real browser smoke of clean first run, exam creation, and English/German switching using disposable synthetic data.

## Verified commands

- Backend/API: 28 tests passed, including PDFium text, image, rendering, and concurrent-import regressions.
- Current domain suite: 65 tests passed. Obsolete Flask/global-index tests were replaced or removed with the obsolete features; desktop pagination/source-page coverage has 4 passing tests.
- Frontend: translation parity, component utility tests, TypeScript and production build passed.
- Frozen Intel macOS sidecar: rebuilt and self-tested against PDF/Markdown import, SQLite, FAISS, API access and packaged prompts. Removed dependencies are excluded; its collected runtime notices include PDFium native notices.
- Runtime dependency audit: no known vulnerabilities found in the collected Python inventory; production JavaScript audit found zero vulnerabilities.
- Rust: `cargo check --locked` passed with Rust 1.90.
- JavaScript dependencies: `npm audit --audit-level=high` found zero vulnerabilities.

## Externally blocked or not yet proven

- No DMG or Windows EXE was built in this pass; installer paths and sizes therefore do not exist.
- Apple Silicon, Intel macOS, and Windows clean-machine installation tests remain outstanding.
- The updater public key is a deliberate placeholder. Tauri signing, Apple Developer ID/notarization, and Windows Authenticode secrets are not configured.
- GitHub Actions and release publishing have not run; there is no release URL or downloadable asset yet.
- Real local Ollama PDF→FAISS→generation→practice→backup/restore→restart smoke passed using synthetic data. Signed updates and the cross-platform acceptance matrix remain outstanding.
- Feature screen catalogs are checked for German/English key and interpolation parity. Generated study content and original course passages are not translated retroactively.
- Third-party license inventory/approval for frozen native dependencies remains a release blocker.
