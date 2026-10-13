# Colloquily security review

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
