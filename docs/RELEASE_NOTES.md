# Colloquily 0.1.3 — PDF reader hotfix

Fixes valid lecture PDFs failing to open in the installed 0.1.2 preview.
**This is an unsigned prerelease.**

## Fixed

- The installed app's security policy blocked PDF.js from fetching a temporary
  blob URL. The reader now receives bytes directly from the authenticated local
  backend, avoiding the second fetch. The security policy remains unchanged.
- PDF Retry now actually reloads the document. Note-loading and note-saving
  failures appear separately and no longer incorrectly label the PDF damaged.
- PDF auxiliary asset URLs resolve against the app origin for worker use.
- A release-gating regression checks the production build under the exact
  desktop security policy in Chromium and WebKit: visible PDF rendering,
  authenticated special-character filenames, navigation, page notes/reopen,
  failed PDF retry, and isolated note retry.

## Your data

No database migration or reimport is needed. Existing PDFs, notes, exams,
questions, answers, progress and settings are unchanged. Install this version
and open the existing document again.

## Downloads

- Apple Silicon macOS 14+: `Colloquily_0.1.3_aarch64.dmg`
- Intel macOS 14+: `Colloquily_0.1.3_x64.dmg`
- Windows x64: `Colloquily_0.1.3_x64-setup.exe`
- Matching `licenses-*.zip`, `LICENSE`, `NOTICE` and `SHA256SUMS.txt`

Installers are unsigned and not notarized. Automatic signed updates remain
unavailable for this preview; install the update manually. Do not disable
operating-system security globally. Publication requires all native builds,
real-model acceptance and the new PDF reader regression to pass.
