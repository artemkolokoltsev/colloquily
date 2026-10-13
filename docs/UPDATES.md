# Updates and release signing

Colloquily uses the official Tauri v2 updater. It checks GitHub Releases without blocking startup; study features continue to work offline. Settings shows the installed version and lets the learner check, approve, install, and restart. An update does not write to the workspace data directory.

Updater signatures, Apple signing/notarization, and Windows Authenticode are separate controls. `TAURI_SIGNING_PRIVATE_KEY` signs updater artifacts; only its public key belongs in the app. Apple Developer ID credentials sign and notarize macOS bundles. A Windows certificate signs NSIS.

The committed updater key is intentionally a release-blocking placeholder. Before a production tag, generate a Tauri updater key pair and store the private key, password, and public key as GitHub Actions secrets. The release workflow refuses missing credentials and creates a draft release. Never commit the private key.

Use SemVer tags such as `v0.1.0`. Test an update against a disposable existing workspace containing a source, index, questions, answers, and progress before publishing the draft.
