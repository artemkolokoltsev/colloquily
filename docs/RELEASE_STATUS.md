# v0.1.0 release status

## Implemented and locally tested

- React/Tauri/FastAPI desktop lifecycle, single instance, random loopback port/token, readiness and shutdown handling.
- Empty first workspace, exam isolation, accepted-evidence retrieval, guarded question generation, practice persistence, and extractive fallbacks requiring review.
- German/English detection, persistence, live switching, typed catalogs, and translation-key parity test for the release shell/settings/error path.
- Schema version 10, pre-migration SQLite backups, integrity validation, newer-schema refusal, whole-workspace export/restore validation, source removal/index invalidation.
- Official Tauri v2 updater client, startup/manual checks, approval/progress/restart UI, signed-artifact configuration, native release matrix, and draft GitHub Releases.
- Real browser smoke of clean first run, exam creation, and English/German switching using disposable synthetic data.

## Verified commands

- Backend/API: 23 tests passed.
- Retained domain suite: 75 tests passed.
- Frontend: translation parity and production build passed.
- Rust: `cargo check --locked` passed with Rust 1.90.
- JavaScript dependencies: `npm audit --audit-level=high` found zero vulnerabilities.

## Externally blocked or not yet proven

- No DMG or Windows EXE was built in this pass; installer paths and sizes therefore do not exist.
- Apple Silicon, Intel macOS, and Windows clean-machine installation tests remain outstanding.
- The updater public key is a deliberate placeholder. Tauri signing, Apple Developer ID/notarization, and Windows Authenticode secrets are not configured.
- GitHub Actions and release publishing have not run; there is no release URL or downloadable asset yet.
- The full model-backed PDF→FAISS→generation→practice→update acceptance matrix still requires native runners, installed Ollama models, and signed artifacts.
- Full translation of every feature screen is incomplete; the first-run shell, navigation, exam creation, settings, update/backup UI, progress primitives, and structured errors are localized, while several domain screens still contain English copy.
- Third-party license inventory/approval for frozen native dependencies remains a release blocker.
