# Colloquily v0.1.0-rc.4 — unsigned preview

First public desktop release candidate for local, source-grounded university
oral exam preparation. **This is a prerelease, not a signed production release.**

## Downloads

- Apple Silicon macOS 14+: `Colloquily_0.1.0_aarch64.dmg`
- Intel macOS 14+: `Colloquily_0.1.0_x64.dmg`
- Windows x64: `Colloquily_0.1.0_x64-setup.exe`
- Matching `licenses-*.zip`, `LICENSE`, `NOTICE`, and `SHA256SUMS.txt`

Read [installation](https://github.com/artemkolokoltsev/colloquily/blob/main/docs/INSTALLATION.md),
the [user guide](https://github.com/artemkolokoltsev/colloquily/blob/main/docs/USER_GUIDE.md),
and [license information](https://github.com/artemkolokoltsev/colloquily/blob/main/docs/LICENSING.md).
Download the matching license/source bundle with your installer.

## Included

- React/Tauri desktop interface with a managed local FastAPI sidecar.
- English/German UI, exam-scoped PDF/Markdown import, source review, FAISS retrieval,
  grounded questions, practice, timed simulations and local progress.
- Explicit Ollama setup/downloads; no cloud inference fallback or bundled model weights.
- Validated workspace export/restore, safety backups, schema migration protections,
  and Windows-safe SQLite connection handling.
- Apache-2.0 project license, native/frontend/Python license inventories and
  corresponding MPL-covered sources. PDFium replaces PyMuPDF; AGPL components
  are rejected by the distribution checks.

## Preview limitations

The installers are **not Apple Developer ID signed/notarized or Windows
Authenticode signed**. macOS and Windows may warn or block installation. Do not
disable operating-system security globally. Only test files obtained from this
repository after checking their SHA-256 values, and follow your OS's normal
per-application review controls. If policy blocks unsigned apps, wait for a
signed release.

Automatic updates are not available for this preview; install updates manually.
Clean-machine GUI installation and full hardware coverage are not established by
CI alone. Back up existing workspaces before testing. Original course passages
and previously generated study content are not translated retroactively.

Models require a separate Ollama installation, explicit downloads, sufficient
disk space and compliance with the model provider's terms. Local AI feedback
can be wrong and is not an official exam assessment.
