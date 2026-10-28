# Installing Colloquily

> **Desktop previews are unsigned prereleases.** Download published installers under [GitHub Releases](https://github.com/artemkolokoltsev/colloquily/releases), not an unverified Actions artifact. Signed production installers are not available yet.

Download your platform's installer and matching `licenses-*.zip`, then compare
the installer SHA-256 with `SHA256SUMS.txt`. macOS/Windows may warn or refuse
unsigned software. Only use files from this repository after reviewing their
origin and checksum. Do not disable system security globally; if your policy
blocks unsigned apps, wait for a signed release. Versions through 0.1.5 require a manual upgrade to 0.1.6. From 0.1.6 onward, update artifacts are cryptographically signed and can install automatically; OS signing/notarization remains a separate requirement. See [permanent downloads and updates](DOWNLOADS.md).

## macOS

Colloquily targets macOS 14 or newer. Choose `Colloquily_<version>_aarch64.dmg` for Apple Silicon or `Colloquily_<version>_x64.dmg` for Intel. Mount the DMG, drag Colloquily to Applications, and open it. A production release must be signed with an Apple Developer ID and notarized; unsigned previews are not.

## Windows

Choose `Colloquily_<version>_x64-setup.exe` for 64-bit Windows. The NSIS installer installs for the current user. A production installer must carry an Authenticode signature; unsigned previews do not. WebView2 is normally present on supported Windows systems; the installer can arrange it when needed.

## Local AI

Open **AI setup** for the guided installation and readiness flow. If Ollama is
missing, use the official download link and complete its installer. **Start local
AI** starts an existing installation; it never executes an installation script.
Review the recommended model/space estimate, download models, and run the local
readiness test. No terminal is needed. Ollama models live outside workspace
backups. Organizing materials remains available before AI setup is complete.

For publisher verification and Apple Developer ID setup, see
[trusted releases](TRUSTED_RELEASES.md). The 0.1.6 installers remain OS-unsigned;
adding credentials affects only newly built releases.

Mutable data is stored in `~/Library/Application Support/Colloquily/` on macOS and `%APPDATA%\Colloquily\` on Windows. Installing a newer application version does not replace this directory.
