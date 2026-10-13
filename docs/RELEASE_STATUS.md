# v0.1.0 release status

## Implemented and locally tested

- React/Tauri/FastAPI desktop lifecycle, single instance, random loopback port/token, readiness and shutdown handling.
- Empty first workspace, exam isolation, accepted-evidence retrieval, guarded question generation, practice persistence, and extractive fallbacks requiring review.
- German/English detection, persistence, live switching, typed catalogs, and translation-key parity test for the release shell/settings/error path.
- Schema version 10, pre-migration SQLite backups, integrity validation, newer-schema refusal, whole-workspace export/restore validation, source removal/index invalidation.
- Official Tauri v2 updater client, startup/manual checks, approval/progress/restart UI, signed-artifact configuration, native release matrix, and draft GitHub Releases.
- Real browser smoke of clean first run, exam creation, and English/German switching using disposable synthetic data.

## Verified commands

- Backend/API/distribution: 36 tests passed, including PDFium import, Windows-safe SQLite handle checks, AGPL rejection, copyright-text preservation, and MPL source-archive regressions.
- Current domain suite: 65 tests passed. Obsolete Flask/global-index tests were replaced or removed with the obsolete features; desktop pagination/source-page coverage has 4 passing tests.
- Frontend: translation parity, component utility tests, TypeScript and production build passed.
- Frozen Intel macOS sidecar: rebuilt and self-tested against PDF/Markdown import, SQLite, FAISS, API access and packaged prompts. Removed dependencies are excluded; its collected runtime notices include PDFium native notices.
- Runtime dependency audit: no known vulnerabilities found in the collected Python inventory; production JavaScript audit found zero vulnerabilities.
- Rust: `cargo check --locked` passed with Rust 1.90.
- JavaScript dependencies: `npm audit --audit-level=high` found zero vulnerabilities.

## Externally blocked or not yet proven

- Windows x64 EXE, Apple Silicon DMG and Intel DMG native builds pass. The release-candidate tag pipeline rebuilds them with full license resources and publishes the three installers, three license/source ZIPs, LICENSE, NOTICE and SHA256SUMS only after every native job succeeds.
- Apple Silicon, Intel macOS, and Windows clean-machine installation tests remain outstanding.
- The updater public key is a deliberate placeholder. Tauri signing, Apple Developer ID/notarization, and Windows Authenticode secrets are not configured.
- Native CI evidence: [three-platform successful build](https://github.com/artemkolokoltsev/colloquily/actions/runs/38443257634). Public preview: [v0.1.0-rc.1](https://github.com/artemkolokoltsev/colloquily/releases/tag/v0.1.0-rc.1). Publication is gated on the new license-inclusive native build; the workflow never marks this as a signed stable release.
- Real local Ollama PDF→FAISS→generation→practice→backup/restore→restart smoke passed using synthetic data. Signed updates and the cross-platform acceptance matrix remain outstanding.
- Feature screen catalogs are checked for German/English key and interpolation parity. Generated study content and original course passages are not translated retroactively.
- Apache-2.0 is adopted for original project code. Distribution checks collect Python/native, target-specific Rust and production frontend licenses, reject AGPL dependencies and missing license texts, and package notices plus MPL-covered sources. See [licensing](LICENSING.md).
