# Colloquily 0.1.4 — Responsive workspace

The workspace now centers beside the sidebar on large monitors. Pages use the
available workspace width, with smaller padding on narrow windows.

The production browser regression verifies layouts from 390px to 3440px in
Chromium and WebKit, including an open PDF reader, and checks for horizontal
page overflow. This release also includes the PDF loading fix from 0.1.3.

No database migration is needed. Existing documents, notes and learning data
are preserved.

## Downloads

- Apple Silicon macOS 14+: `Colloquily_0.1.4_aarch64.dmg`
- Intel macOS 14+: `Colloquily_0.1.4_x64.dmg`
- Windows x64: `Colloquily_0.1.4_x64-setup.exe`
- Matching license archives, `LICENSE`, `NOTICE` and `SHA256SUMS.txt`

This is an unsigned preview. Install the update manually; signed automatic
updates are unavailable. Publication requires all three native builds,
real-model learning acceptance and the production PDF/browser regression.
