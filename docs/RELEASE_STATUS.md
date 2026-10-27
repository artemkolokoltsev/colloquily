# Release status

Prepared candidate: **0.1.6 — focused practice and reliable updates**.
Local branch: `release/0.1.6`. Tag: `v0.1.6-rc.1`.
See [release notes](RELEASE_NOTES_0.1.6.md), [website URLs](DOWNLOADS.md), and
[the user guide](USER_GUIDE.md).

## Verified locally

- 93 backend/API/distribution regressions: 87 existing full-suite tests plus
  six release-channel/manifest tests; 65 core tests and 11 frontend tests passed.
- Version agreement, English/German translation parity, TypeScript/Vite build,
  and locked Rust check passed. All three release workflow YAML files parse.
- Chromium and WebKit production-CSP regressions passed: PDF rendering, notes,
  formulas, source recovery, onboarding, eight illustrated mode dialogs, research
  links, model selection, English/German, focused answer submission, separate
  feedback, completion, return navigation and bottom-right version footer.
  Light/dark screenshots were inspected.
- A real Tauri signature verified against the committed public trust key.
  Lifecycle tests cover concurrent checks, corrupt/failed downloads, busy
  workspaces, server-side refusal, restart failure and retry without reinstalling.
- The Intel macOS frozen backend rebuilt in the dedicated release environment
  and passed its API/PDF/Markdown/SQLite/FAISS self-test and lifecycle smoke
  (authenticated loopback access and parent-exit shutdown). The general development
  environment failed its license gate, so it was not used for release packaging.
- Permanent Apple Silicon, Intel and Windows links all returned HTTP 200.
  `downloads.json` currently identifies the published `v0.1.5-rc.1` bootstrap.
- Repository updater signing secrets are configured. Only the public key is
  committed; see DOWNLOADS.md for private-key recovery and custody.

## Push to build and publish

```bash
git push --atomic -u origin release/0.1.6 v0.1.6-rc.1
```

The release-candidate tag triggers `.github/workflows/desktop.yml`, building
macOS Apple Silicon, macOS Intel and Windows x64. Publication waits for native
builds, backend/core tests, real local-model learning acceptance and browser
regressions. It publishes installers, signed update payloads, platform signatures,
license/source bundles, checksums and `latest.json`, then refreshes fixed website
links under the rolling `latest` tag. A branch-only push does not publish.

The commit/tag are prepared locally, not pushed. Native 0.1.6 CI and installation
on all target machines remain to be verified after the push. Preview installers
are still OS-unsigned: updater signatures do not provide Apple notarization or
Windows Authenticode. A complete native update/install/relaunch cycle must be
validated with a subsequent higher-version build after 0.1.6 bootstrap.

Users of 0.1.5 or earlier need one manual upgrade. The rolling channel has manual
downloads now; its signed update feed appears only after 0.1.6 passes and publishes.
Merge the download-channel workflow to the default branch for manual promotion
and future stable-release publication triggers. Preview promotion already runs
directly from the tagged release branch.
