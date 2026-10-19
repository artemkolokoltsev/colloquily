# Colloquily 0.1.2 — unsigned desktop preview

A product UX and reliability update. **This is an unsigned prerelease.**
Publication requires real-model learning acceptance and native builds for all
three supported targets to pass on this release revision.

## What changed

- Five primary destinations: Home, Materials, Practice, Ask and Settings.
  Home combines progress and daily goals; the learning plan expands on demand.
  Manage Questions is a secondary Practice view.
- Offline PDF reader with page navigation, zoom, fit-width, text search and
  remembered pages. Personal page notes autosave to SQLite and survive restart.
- Notes remain separate from lecture evidence. Ask can include them on explicit
  opt-in, with distinct student-annotation citations.
- Clear slide headings propagate to body text; normalized topic names are reused.
  Question classification respects exam ownership and ambiguous cases stay
  unassigned. Manual assignment and safe background repair are available.
- Skipped questions earn zero without invoking AI, show expected answer points,
  and remain separate from evaluated-answer averages and topic mastery.
  Expandable answer history supports loading older attempts.
- Exam-scoped AI readiness reuses compatible installed models, avoids repeated
  setup prompts and serializes downloads. Materials and Home load less data.
- English/German labels, adaptive light/dark layouts, reduced motion and keyboard
  navigation are retained.

## Data and compatibility

Schema 11 adds page-note storage and manual-topic provenance. Existing exams,
PDFs, questions, answers, correction history, indexes and settings are preserved.
The migration takes a validated database backup first. The application identity
and persistent data directory are unchanged.

## Downloads

- Apple Silicon macOS 14+: `Colloquily_0.1.2_aarch64.dmg`
- Intel macOS 14+: `Colloquily_0.1.2_x64.dmg`
- Windows x64: `Colloquily_0.1.2_x64-setup.exe`
- Matching `licenses-*.zip`, `LICENSE`, `NOTICE` and `SHA256SUMS.txt`

Download the matching license/source archive alongside the installer and verify
its SHA-256 checksum. See [installation](https://github.com/artemkolokoltsev/colloquily/blob/main/docs/INSTALLATION.md)
and [licensing](https://github.com/artemkolokoltsev/colloquily/blob/main/docs/LICENSING.md).

## Preview limitations

Installers are not Apple Developer ID signed/notarized or Windows Authenticode
signed. Operating systems may warn or block installation; do not disable system
security globally. Automatic signed updates are not enabled for this preview.

Image-only PDFs need an external OCR step. Notes are text only. Optional note
retrieval uses bounded text matching in Ask; it does not feed automatic question
generation. Generated study quality still depends on the local model and source
coverage. A practice score does not guarantee exam readiness.

Detailed root causes, changes and verification:
[0.1.2 implementation report](https://github.com/artemkolokoltsev/colloquily/blob/v0.1.2-rc.1/docs/RELEASE_NOTES_0.1.2.md).
