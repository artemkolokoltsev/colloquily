# Colloquily 0.1.10 — Sidebar sized to your window

- Keep the desktop sidebar at the window height while the main page scrolls.
- Keep the exam picker and About/version footer visible. In short windows, navigation and Advanced tools scroll independently. Narrow layouts continue to show navigation above the page; focused practice still hides it.
- Fix an evaluation polling race so a completed response includes the final saved grade, even when grading finishes during the request.
- Refresh README UI references and explain all eight practice modes, feedback timing and source-checking limitations.
- Add architecture, engineering standards, case studies and an observed engineering baseline.

## Preview and updates

Existing course materials, settings and practice history are preserved. No database schema or AI generation/grading rules change.

This preview uses signed updater payloads. Operating-system publisher trust is reported separately in each platform's trust asset; updater signatures do not establish Apple notarization or Windows Authenticode.

Permanent download links stay the same. Version 0.1.6 and later can receive this version through the signed updater; earlier versions need a manual download.

Local verification before tagging: 126 backend/API tests, 65 domain tests, 17 frontend tests, version/translation checks, production build, locked Rust check, and Chromium/WebKit smoke checks. The browser checks include scrolling, short-window navigation and narrow layout. Native installers and real-model acceptance are checked by the tagged workflow before publication.
