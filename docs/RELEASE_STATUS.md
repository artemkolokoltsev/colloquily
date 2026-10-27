# Release status

Release candidate: **0.1.9 — Source insights and clearer session review**.
Branch `release/0.1.9`; tag `v0.1.9-rc.1`.

Includes the complete question-quality, PDF insight, results, timer, session-closing,
About, progress and Settings changes described in [release notes](RELEASE_NOTES_0.1.9.md).

Local verification passed: 124 backend/API tests, 65 core tests, 17 frontend tests,
translation checks, production build, Rust check, and Chromium/WebKit regressions.

Publication is authorized. The tagged workflow builds all three native installers,
runs real-model learning acceptance, and publishes only after the required jobs pass.
Confirm publication from the workflow and release assets, not merely the tag push.
Permanent download URLs and the updater feed are promoted after publication.

OS publisher trust depends on configured signing credentials and is reported
per platform. See [TRUSTED_RELEASES.md](TRUSTED_RELEASES.md) and [DOWNLOADS.md](DOWNLOADS.md).
