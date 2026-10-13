# Installing Colloquily

> **v0.1.0-rc.4 is an unsigned preview.** It is published under [GitHub Releases](https://github.com/artemkolokoltsev/colloquily/releases), not just Actions artifacts. Signed production installers are not available yet.

Download your platform's installer and matching `licenses-*.zip`, then compare
the installer SHA-256 with `SHA256SUMS.txt`. macOS/Windows may warn or refuse
unsigned software. Only use files from this repository after reviewing their
origin and checksum. Do not disable system security globally; if your policy
blocks unsigned apps, wait for a signed release. Preview updates are manual.

## macOS

Colloquily targets macOS 14 or newer. Choose `Colloquily_0.1.0_aarch64.dmg` for Apple Silicon or `Colloquily_0.1.0_x64.dmg` for Intel. Mount the DMG, drag Colloquily to Applications, and open it. A production release must be signed with an Apple Developer ID and notarized; this preview is not.

## Windows

Choose `Colloquily_0.1.0_x64-setup.exe` for 64-bit Windows. The NSIS installer installs for the current user. A production installer must carry an Authenticode signature; this preview does not. WebView2 is normally present on supported Windows systems; the installer can arrange it when needed.

## Local AI

Install [Ollama](https://ollama.com/download), start it, then open **AI setup** in Colloquily. Model downloads are explicit and show progress. Model weights live in Ollama's model directory and are not included in Colloquily installers or backups. Exam creation and material organization remain available without Ollama.

Mutable data is stored in `~/Library/Application Support/Colloquily/` on macOS and `%APPDATA%\Colloquily\` on Windows. Installing a newer application version does not replace this directory.
