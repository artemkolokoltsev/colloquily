# Release status

Published preview: **0.1.10 — Sidebar sized to your window**.
Tag [`v0.1.10-rc.2`](https://github.com/artemkolokoltsev/colloquily/releases/tag/v0.1.10-rc.2), source commit `5a18d8c4caf5eb6d0c1cf45e4e90792218090fee`.
Published on 2026-10-28. Branch: `release/0.1.10`.

Includes the viewport-height sidebar fix, documentation refresh and evaluation
completion-response race fix described in [release notes](RELEASE_NOTES_0.1.10.md).
No database schema or AI generation/grading rules change.

[Release workflow](https://github.com/artemkolokoltsev/colloquily/actions/runs/40693994035)
passed Windows x64, Intel macOS and Apple Silicon builds, frozen-backend checks,
browser regressions, real-model learning acceptance and publication. All platforms
ran 126 backend/API, 65 domain and 17 frontend tests plus version/translation checks.

The first candidate was stopped after CI exposed the evaluation response race;
two deterministic regressions reproduce it and pass with the fix. The corrected
candidate's Apple Silicon runner provisioning initially failed for hosted capacity;
its retry passed without source changes. Existing tags were not replaced.

Public verification after publication: all three permanent installer URLs returned
HTTP 200; `downloads.json` names `v0.1.10-rc.2` / `0.1.10`; `latest.json` serves
`0.1.10` with signed, immutable versioned payload references for all three targets.
See [permanent downloads](DOWNLOADS.md).

This remains a preview. Updater signatures are separate from operating-system
publisher trust; per-platform trust reports are included with the release.
Clean-machine GUI installation was not performed as part of this patch.
See [TRUSTED_RELEASES.md](TRUSTED_RELEASES.md).
