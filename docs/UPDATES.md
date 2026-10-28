# Updates and release signing

Colloquily uses the official Tauri v2 updater. It checks GitHub Releases without blocking startup; study features continue to work offline. About Colloquily provides version and update controls. Since 0.1.6, automatic updates can download a signed payload and install after an idle period and countdown. Active practice, background work and unsaved Home edits block automatic restart. A workspace backup is created before installation; application replacement preserves the separate workspace. See the [user guide](USER_GUIDE.md#updates-and-troubleshooting) for controls and retry behavior.

Updater signatures, Apple signing/notarization, and Windows Authenticode are separate controls. `TAURI_SIGNING_PRIVATE_KEY` signs updater artifacts; only its public key belongs in the app. Apple Developer ID credentials sign and notarize macOS bundles. A Windows certificate signs NSIS.

The app configuration contains the public updater key and GitHub update-feed endpoint. The matching private key and password belong in GitHub Actions secrets, never in the repository. Release workflows validate signing prerequisites; the presence of a public key alone does not establish that a particular release was successfully signed or published. Check the release's assets and [native trust evidence](TRUSTED_RELEASES.md). Older previews at 0.1.5 or earlier need one manual installation of 0.1.6 or later to enter this update channel.

Use SemVer tags such as `v0.1.0`. Test an update against a disposable existing workspace containing a source, index, questions, answers, and progress before publishing the draft.
