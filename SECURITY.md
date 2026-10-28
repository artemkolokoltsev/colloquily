# Security policy

Colloquily is a single-user local desktop app. Keep exam documents, indexes,
answers and model inference on the user's machine. It is not a public API or a
multi-user service. Only the latest published preview receives fixes; older
downloads remain available without a promise of backported security patches.

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/artemkolokoltsev/colloquily/security/advisories/new)
when enabled. If unavailable, open an issue asking for a private reporting
channel, without exploit details or sensitive attachments. Private reporting
activation is tracked in [repository maintenance](docs/REPOSITORY_MAINTENANCE.md);
this policy does not imply it has already been enabled.

Include the application version, OS/architecture, affected component, impact and
minimal reproduction using synthetic material. Never attach personal course
PDFs, answers, databases, tokens, signing keys or full unsanitized logs. There is
no guaranteed response time for this solo-maintainer project.

## Boundaries and updates

The desktop backend binds to loopback and requires a per-launch token; Host,
Origin and file paths are checked. Local inference is restricted to loopback.
Do not expose the listener through proxies or tunnels. Dependencies and model
outputs remain untrusted. See the [security review](docs/security-review.md),
[privacy policy](docs/PRIVACY.md), and [architecture](docs/ARCHITECTURE.md).

Version tags and published artifacts are preserved. Verify installer checksums
and release-specific trust evidence. Tauri updater signatures authenticate
updates; they do not establish Windows publisher trust or Apple notarization.
Dependency update PRs must pass checks and preserve target-specific license
inventories; a green dependency alert is not proof of application security.
