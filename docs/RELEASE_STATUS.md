# Release status

Published preview: **0.1.12 — Material formatting and responsive source review**.
Tag [`v0.1.12-rc.1`](https://github.com/artemkolokoltsev/colloquily/releases/tag/v0.1.12-rc.1),
source commit `cd80a58c2ac3e9540d22ddd4e22cf656302693c5`.
Published on 2026-11-05 through the existing live download/update channel.

Material review now fetches ten passages at a time, preserves extracted line
breaks and loads original PDF previews only on request. Closed views unmount
heavy content while corrections and the current passage page remain in the
Materials workspace. Contents pages are reference material rather than study
evidence. Existing extracts benefit from the display fix without reprocessing;
no database schema change is required. See [release notes](RELEASE_NOTES_0.1.12.md)
and [user guide](USER_GUIDE.md).

[Release workflow](https://github.com/artemkolokoltsev/colloquily/actions/runs/42093259854)
passed Windows x64, Intel macOS and Apple Silicon builds, frozen-backend checks,
Chromium/WebKit reader and coursework regressions, real-model learning acceptance
and publication. All platforms ran 140 backend/API, 70 domain and 17 frontend
tests. The local deterministic gate also passed 7 release-tooling tests, static
checks and the production build (234 tests in total).

The browser regression covers a thousand-passage library: only ten cards mount,
scrolling creates no additional passage or PDF requests, and original pages load
only on request. Source line breaks, math and Markdown tables are checked.
Additional regressions verify corrections survive closing Details or Advanced
tools, including later pages and failed saves. The PR browser job's first attempt
timed out downloading Ubuntu dependencies; its retry passed without source
changes. The tagged release workflow passed on its first attempt. No published
tag or payload was replaced.

Public verification after publication:

- All three permanent installer URLs returned HTTP 200.
- `downloads.json` names `v0.1.12-rc.1` / `0.1.12`.
- `latest.json` serves `0.1.12` with immutable versioned update URLs for all three
  platforms; its signatures match the published signature assets.
- The downloaded Intel Mac app archive matched its published SHA-256 checksum,
  and the app bundle reports version `0.1.12`.
- The backend extracted from that public archive passed its self-test, including
  the bounded review API, PDF/Markdown, SQLite, FAISS filtering and coursework.

See [permanent downloads](DOWNLOADS.md). This remains an updater-signed preview.
Per-platform trust reports record `os_signed: false` and `notarized: false`;
updater signatures do not establish OS publisher trust. Clean-machine GUI
installation on all platforms was not performed. Tests cover the checked
scenarios and do not guarantee zero defects.
See [TRUSTED_RELEASES.md](TRUSTED_RELEASES.md).
