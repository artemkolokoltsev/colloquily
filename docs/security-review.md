# Colloquily security review

## Repository maintenance review — 2026-10-28

This scoped follow-up inspected the FastAPI/React local boundary and release
workflow credentials; it is not a penetration test or full dependency audit.
No new critical/high application vulnerability was confirmed. The existing
runtime protections remain unchanged: `backend/launcher.py:31` binds loopback,
`backend/main.py:37-48` checks Host/Origin/token, and
`backend/services/models.py:65-68` rejects nonlocal inference endpoints.
Tracked binary document inventory contains the synthetic reader test PDF;
no tracked SQLite database or private-key extension was found. This extension
scan does not prove absence of secrets or confidential text.

Repository findings, in maintenance priority order:

- **REPO-001 — Medium:** main was unprotected (`26add3e`), with no rulesets.
  `.github/protect-main.json` supplies the reviewed policy; activation requires
  administrator tooling after `verify` has passed on main. It is not applied by
  committing the JSON. See [maintenance](REPOSITORY_MAINTENANCE.md).
- **REPO-002 — Low:** action major-version tags were mutable. Workflow references
  now pin resolved upstream SHAs for checkout/setup/artifacts, certificate import
  and Tauri publication. The Rust action retains its verified toolchain-version
  reference; monthly Dependabot checks track action updates.
- **REPO-003 — Low:** no dependency update automation or private-reporting policy
  existed. Monthly grouped Dependabot updates and root `SECURITY.md` are added;
  vulnerability alerts/private reporting still need administrator activation.

`npm` reported zero vulnerabilities after tooling installation. Python uses
bounded requirements rather than a complete resolved lock; no fresh Python or
Cargo advisory audit is claimed. Release write permissions remain restricted to
tag/channel publication workflows/jobs; no `pull_request_target` workflow exists.
The original controls/release notes below are historical observations. In
particular SEC-001 predates implemented frozen/target license inventories:
`scripts/release_notices.py` and release workflow artifact steps now produce them.
This review does not independently approve every published native dependency.

Review used the
[security-best-practices skill](/Users/artem.kolokoltsev/.codex/skills/security-best-practices/SKILL.md).

## Executive summary

The desktop boundary is appropriately local-first: the API binds to loopback, validates Host and browser Origin, and packaged requests require a random launch token. No frontend HTML injection or dynamic-code sinks were found. Uploaded source names and retrieval paths are constrained, outbound model endpoints must be loopback, updater transport is HTTPS, and dependency audit currently reports zero vulnerabilities.

No unresolved critical or high-severity application finding was confirmed in the reviewed React/FastAPI desktop path.

## Controls verified

- **FASTAPI-AUTH-001 / local process boundary:** `backend/main.py:30-41` centralizes Trusted Host, strict CORS/Origin, and launch-token enforcement. Health is intentionally unauthenticated and reveals only readiness.
- **FASTAPI-FILES-001:** `backend/api/routes.py:90-106` sanitizes upload names, allowlists extensions, refuses replacement, caps each source at 100 MB, and uses the exam-scoped path resolver for retrieval. Responses use `nosniff`; Markdown is served as plain text.
- **FASTAPI-SSRF-001:** `backend/main.py:20-21` rejects model endpoints that are not loopback before the API starts.
- **REACT-XSS-001:** the React source contains no `dangerouslySetInnerHTML`, direct HTML injection, `eval`, string-code execution, or untrusted navigation sinks. User and model content is rendered as escaped JSX text.
- **Desktop least privilege:** `src-tauri/capabilities/default.json` exposes only core, updater, and restart permissions to the webview. Sidecar launch and the fixed Ollama download URL remain Rust commands (`src-tauri/src/main.rs:25-40`).
- **Supply chain:** `npm audit --audit-level=high` reports zero findings. Rust dependencies are locked. Python constraints bound major versions; native-release license review remains required before redistribution.

## Remaining release checks

### SEC-001 — Medium — Native dependency licenses not yet approved

- **Location:** `backend/requirements-desktop.txt`, packaged PyInstaller dependency graph.
- **Impact:** distributing native libraries without completing all license notices could create release obligations. PyMuPDF was replaced by PDFium and removed from dependencies; the frozen inventory rejects AGPL dependencies.
- **Fix:** produce the final frozen dependency inventory and third-party notices, then obtain project-owner approval before publishing installers.
- **Status:** release blocker; it cannot be truthfully resolved from source inspection alone.

### SEC-002 — Low — Browser-development API has no launch token

- **Location:** `backend/main.py:38-41`.
- **Evidence:** token enforcement activates only when `COLLOQUILY_API_TOKEN` is supplied; the Tauri launcher always supplies one.
- **Impact:** another local process could call the development API. Remote hosts cannot connect because the launcher binds `127.0.0.1`, and foreign browser origins are rejected.
- **Mitigation:** documented development-only behavior. Do not expose the development port through a proxy or non-loopback bind.
