# Release status

Release candidate: **0.1.8 — Chat and automatic practice evaluation**.
Branch `release/0.1.8`; tag `v0.1.8-rc.1`.

Includes all prepared 0.1.7 changes plus the practice, chat and sidebar fixes.
Local validation passed: 117 backend/API tests, 65 core tests, 11 frontend tests,
translation parity, production build, and Chromium/WebKit browser checks.

Publication is authorized. The tagged GitHub workflow builds macOS Apple Silicon,
macOS Intel and Windows installers, runs acceptance checks, then publishes the
preview and promotes the permanent download links. Publication must be verified
from the completed workflow and release assets; pushing a tag alone is not success.

Native publisher trust is reported per platform. Missing OS signing credentials
produce an OS-unsigned preview with signed updater payloads. See
[TRUSTED_RELEASES.md](TRUSTED_RELEASES.md) and [DOWNLOADS.md](DOWNLOADS.md).
