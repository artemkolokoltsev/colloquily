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

Install [Ollama](https://ollama.com/download) and start it. Version 0.1.1 prepares suitable local models automatically for the selected exam, with progress, cancellation and retry; explicit exam model settings remain authoritative. Advanced controls are under **AI setup**. Version 0.1.0 requires explicit model downloads there. Model weights live in Ollama's model directory and are not included in installers or backups. Exam creation and material organization remain available without Ollama.

Mutable data is stored in `~/Library/Application Support/Colloquily/` on macOS and `%APPDATA%\Colloquily\` on Windows. Installing a newer application version does not replace this directory.
