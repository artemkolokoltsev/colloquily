# Colloquily 0.1.1 — unsigned desktop preview

UX and learning-quality patch following the 0.1.0 previews.
**This is a prerelease, not a signed production release.** Publishing requires
successful real-model synthetic acceptance and all three native build jobs.

## Downloads

- Apple Silicon macOS 14+: `Colloquily_0.1.1_aarch64.dmg`
- Intel macOS 14+: `Colloquily_0.1.1_x64.dmg`
- Windows x64: `Colloquily_0.1.1_x64-setup.exe`
- Matching `licenses-*.zip`, `LICENSE`, `NOTICE`, and `SHA256SUMS.txt`

Read [installation](https://github.com/artemkolokoltsev/colloquily/blob/main/docs/INSTALLATION.md),
the [user guide](https://github.com/artemkolokoltsev/colloquily/blob/main/docs/USER_GUIDE.md),
and [license information](https://github.com/artemkolokoltsev/colloquily/blob/main/docs/LICENSING.md).
Download the matching license/source bundle with your installer.

## What changed

- Searchable exam picker, quieter desktop navigation, adaptive light/dark appearance,
  English/German workflows and clearer material/source review.
- Resource-aware local model preparation with installed-model reuse, download
  progress/cancellation/retry and preservation of explicit exam settings.
- All-document/topic question preparation with exact source quotes, grounded
  answer points, comparison checks and semantic/rubric duplicate rejection.
  No passage-quotation starter fallback or unrelated-question examples.
- Bounded incremental generation and explicit partial coverage when the local
  model cannot produce enough valid questions. Valid results are retained.
- Skip advances without AI evaluation or answer feedback. Repeated submissions
  are idempotent; delayed answers cannot grade the next question.
- Reprocessing preserves unchanged citation IDs and manual review decisions.
  Stale sources do not count toward active practice or current coverage.
- Existing application identity, workspace paths and schema version are retained.
  Backup/restore, historical questions, answers and progress remain supported.
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

Ollama is a separate, guided installation; Colloquily does not silently install
executables. Missing selected model weights are prepared automatically and can
be cancelled. Downloads require sufficient disk space and compliance with the
model provider's terms. Inference remains local; no cloud AI fallback is used.
Small/CPU-only models can be slow or fail coverage checks. Scanned PDFs need OCR
prepared separately; diagram interpretation and complex formula reconstruction
are not automatic. Review generated study content against its cited source.
Local AI feedback can be wrong and is not an official exam assessment.
