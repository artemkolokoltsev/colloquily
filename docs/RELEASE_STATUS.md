# Release status

Published preview: **0.1.11 — Lecture script revisions and exercise submissions**.
Tag [`v0.1.11-rc.1`](https://github.com/artemkolokoltsev/colloquily/releases/tag/v0.1.11-rc.1),
source commit `de73369088b3ec6c7fbfa00dda12a4aff939715a`.
Published on 2026-11-05 through the existing live download/update channel.

Includes one evolving script per course with archived PDFs/page notes, a LaTeX
exercise workspace, configurable submission headers and local PDF export.
See [release notes](RELEASE_NOTES_0.1.11.md) and [user guide](USER_GUIDE.md).
Schema 12 is additive and preserves existing course data with a pre-upgrade
database snapshot. PDF compilation requires a local TeX installation.

[Release workflow](https://github.com/artemkolokoltsev/colloquily/actions/runs/42038654246)
passed Windows x64, Intel macOS and Apple Silicon builds, frozen-backend checks,
Chromium/WebKit reader and coursework regressions, real-model learning acceptance
and publication. All platforms ran 135 backend/API, 70 domain and 17 frontend
tests. The local deterministic gate also passed 7 release-tooling tests, static
checks and the production build.

The tagged coursework job initially timed out downloading TeX packages from an
Ubuntu mirror, before application tests ran. Its retry passed without source
changes and publication remained gated on that result. No version tag or
published payload was replaced.

Public verification after publication:

- All three permanent installer URLs returned HTTP 200.
- `downloads.json` names `v0.1.11-rc.1` / `0.1.11`.
- `latest.json` serves `0.1.11` with immutable versioned update URLs for all three
  platforms; its signatures match the published signature assets.
- The downloaded Intel Mac app archive matched its published SHA-256 checksum.
- The backend extracted from that public archive passed the real coursework
  workflow in Chromium and WebKit: upload, recovery draft, save, `.tex`/PDF
  export, rendered submission preview and script replacement. Its cold start
  required the existing sidecar smoke test's longer startup allowance.

See [permanent downloads](DOWNLOADS.md). This remains an updater-signed preview.
Per-platform trust reports record `os_signed: false` and `notarized: false`;
updater signatures do not establish OS publisher trust. Clean-machine GUI
installation on all platforms was not performed. Test results cover the checked
scenarios and do not guarantee zero defects.
See [TRUSTED_RELEASES.md](TRUSTED_RELEASES.md).
