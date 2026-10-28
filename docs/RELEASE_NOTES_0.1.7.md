# Colloquily 0.1.7 — Guided local AI setup and verified publisher trust

AI setup now guides you through installing/starting Ollama, reviewing recommended
models and their space estimate, downloading them, and testing local AI before
returning to your materials. No terminal is needed. The first-time Ollama
installer still comes from its official website; Colloquily does not silently
install third-party software.

- Start an existing Ollama installation from the app. Setup detects when the
  runtime becomes available and handles slow startup with a retry path.
- Model recommendations remain visible before Ollama is running. Large model
  downloads require an explicit setup action; opening an exam or uploading a
  document no longer implicitly downloads models.
- The readiness sample tests generation and embeddings without your documents
  or personal answers. It reports elapsed generation time and flags a slow sample.
- Advanced model selection remains available, including existing explicit exam
  settings and alternative local backends.
- Mac preview builds can use Developer ID signing/notarization independently of
  Windows signing. Partially configured credentials fail early. Native checks
  must pass before release metadata can claim publisher trust.
- Release assets include per-platform trust reports, also exposed in website
  download metadata. Missing trust records must be treated as unverified.

## Signing status

The code supports native signing, but no valid Developer ID identity or Apple
notarization secrets were available during preparation. An Apple Developer
membership alone does not sign an app. Follow [trusted release setup](TRUSTED_RELEASES.md)
before pushing if this release should be Mac-signed. Windows publisher signing
also requires separate credentials. Without them the platform remains an
OS-unsigned preview, clearly reported as such; updater signatures remain enabled.

The already-published 0.1.6 release and permanent website links remain intact.
Users on 0.1.6 can receive this higher-version update through the signed updater
once this release passes CI. Users on 0.1.5 and earlier require one manual upgrade.
