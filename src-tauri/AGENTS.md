# Desktop shell-specific instructions

Applies to `src-tauri/`. Read root `AGENTS.md` and `docs/desktop.md`.

- Rust/Tauri owns application lifecycle and the bundled Python sidecar. Do not move shell execution into the webview.
- Keep the backend bound to a random **loopback-only** port and use a per-launch token for authenticated API calls.
- Preserve single-instance behavior, startup/error feedback, child shutdown, and cleanup after unexpected exits. Avoid orphaned sidecars.
- Keep capabilities least-privileged; review every new Tauri command, permission and network access.
- Data belongs in OS application-data directories or an explicit workspace override, never beside installed application binaries.
- Native sidecars must be built on matching target OS/architecture; do not claim cross-platform functionality from `cargo check` alone.
- Installer/update changes require signing, third-party notices, checksum and clean-machine validation before a production release.

Run `cargo check --locked --manifest-path src-tauri/Cargo.toml`. For lifecycle changes, also run sidecar smoke tests and target-native package checks when supported. Clearly report platforms not checked.
