# Release status

Prepared candidate: **0.1.7 — guided local AI setup and verified publisher trust**.
Branch `release/0.1.7`; tag `v0.1.7-rc.1`.
The published **v0.1.6-rc.1** completed all native, browser and real-model learning
checks. Its public release and permanent download metadata were verified as 0.1.6
on 2026-10-27. It does not need to be rebuilt to become visible.

## Local verification for 0.1.7

- 108 backend/API/distribution tests and 65 core tests passed.
- 11 frontend tests, translation parity, TypeScript/Vite build and locked Rust
  check passed. Updated release workflow YAML parses.
- Chromium and WebKit production-CSP regressions passed, including PDFs, formulas,
  focused practice, navigation, model selection and the three-stage AI setup.
  The setup regression checks that no model download begins before explicit action.
- The Intel macOS frozen backend rebuilt and passed its self-test and lifecycle
  smoke (authenticated loopback API and parent-exit shutdown).
- Runtime tests cover already-running Ollama, missing installation, safe local
  CLI startup, custom-port refusal, offline recommendations, synthetic readiness
  tests and prohibition of implicit downloads during material preparation.
- Signing tests reject incomplete credentials, development identities, wrong
  Apple teams and missing notarization tickets. Preview trust records remain false.

## Publication

Before publishing a Mac-trusted build, configure the Apple secrets described in
[TRUSTED_RELEASES.md](TRUSTED_RELEASES.md). This Mac has no valid signing identity;
only updater secrets are currently configured in GitHub. Apple Developer
membership has been confirmed by the maintainer, but certificates/notarization
credentials are still needed. Windows signing credentials are also absent.

```bash
git push --atomic -u origin release/0.1.7 v0.1.7-rc.1
```

This triggers native builds, tests, real-model learning acceptance and publication.
With no OS signing secrets, it publishes updater-signed but OS-unsigned previews.
With all Apple secrets configured, Mac builds must pass signature, team identity,
stapled-ticket and Gatekeeper verification. Windows can remain unsigned without
blocking properly configured Mac builds. Stable production tags require signing
for both platforms.

Changes are prepared locally, not pushed. 0.1.7 native CI, live runtime startup on
each target OS, and a complete installed-app update/restart remain to be verified.
The true Apple signing/notarization path cannot be exercised until credentials
exist. The website URLs remain unchanged; download metadata updates only after
successful publication. See [DOWNLOADS.md](DOWNLOADS.md).
