# Installing Colloquily

> Signed public installers have not been published yet. Do not treat locally built or CI `unsigned` artifacts as production downloads.

## macOS

Colloquily targets macOS 14 or newer on Apple Silicon and Intel. Download the matching DMG, drag Colloquily to Applications, and open it. A production release must be signed with an Apple Developer ID and notarized.

## Windows

Colloquily targets 64-bit Windows through an NSIS per-user installer. A production installer must carry an Authenticode signature. WebView2 is normally present on supported Windows systems.

## Local AI

Install [Ollama](https://ollama.com/download), start it, then open **AI setup** in Colloquily. Model downloads are explicit and show progress. Model weights live in Ollama's model directory and are not included in Colloquily installers or backups. Exam creation and material organization remain available without Ollama.

Mutable data is stored in `~/Library/Application Support/Colloquily/` on macOS and `%APPDATA%\Colloquily\` on Windows. Installing a newer application version does not replace this directory.
