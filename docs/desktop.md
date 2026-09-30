# Desktop packaging and release checklist

Build design follows [Tauri v2 sidecars](https://v2.tauri.app/develop/sidecar/), [single instance](https://v2.tauri.app/plugin/single-instance/), and [PyInstaller usage](https://pyinstaller.org/en/stable/usage.html). Model setup uses the [Ollama streaming pull API](https://docs.ollama.com/api/pull).

## Platform configurations

| OS | Rust target | Artifacts | Configuration |
|---|---|---|---|
| macOS Apple Silicon | aarch64-apple-darwin | .app, .dmg | tauri.conf.json, native sidecar build |
| macOS Intel | x86_64-apple-darwin | .app, .dmg | tauri.conf.json, native sidecar build |
| Windows x64 | x86_64-pc-windows-msvc | NSIS .exe | tauri.conf.json, native sidecar build |

The current macOS bundle requires macOS 14 or newer, matching the FAISS and NumPy wheels used for packaging.

Run the exact build commands in the root README on each native OS. The optional manual GitHub Actions workflow builds these targets without publishing releases. Configuration alone is not evidence of a working installer: run installation, startup, PDF import, indexing, practice, exit and relaunch checks on clean machines without Python or Node.

## Lifecycle

Rust enforces single-instance operation, starts a target-specific backend executable, chooses a loopback port and random token, and waits for health plus an authenticated request. The React startup screen displays startup errors. Child stdout/stderr go to `backend.log` in the data directory. On normal exit Rust writes a shutdown command to stdin, waits briefly, then kills any remaining child. EOF on stdin also requests shutdown if the parent exits unexpectedly. Ingestion checkpoints and SQLite remain durable; interrupted in-memory operations must be retried.

Only Rust can launch the sidecar. JavaScript has no shell execution capability. The API rejects foreign Origin headers and the packaged API requires the launch token. This is a single-user local application, not a hardened multi-user network service. Browser development has no token and must remain loopback-only.

## Verification on the development Mac

The Intel macOS build now includes a PyInstaller self-test that runs before copying the sidecar into `src-tauri/binaries/`. It verifies health, PDF/Markdown ingestion, SQLite, FAISS save/reload, rejection of stale review evidence, and packaged prompt files using disposable data and a deterministic embedder. A packaging-specific OpenMP conflict between FAISS and scikit-learn is resolved in `scripts/colloquily-backend.spec` by consistently bundling FAISS's OpenMP runtime.

For a real listener/shutdown check, run:

```bash
python scripts/smoke_sidecar.py src-tauri/binaries/colloquily-backend-x86_64-apple-darwin
```

Use the corresponding architecture suffix and `.exe` on Windows. This verifies loopback health, launch-token and Origin enforcement, and clean shutdown when the parent input pipe closes. It does not download models or access existing user data.

An unsigned Intel macOS debug `.app` was built and launched with disposable data. Its bundled React UI successfully fetched health, exams, and model status from its automatically launched sidecar. Quitting the application produced a clean Uvicorn shutdown and closed its loopback listener. The separate sidecar lifecycle test also passed token/Origin checks and shutdown on parent EOF. Apple Silicon and Windows artifacts have not been executed on this host.

The source checks comprise 68 existing tests and five focused API tests, including a persisted practice round trip. Browser smoke testing covers exam creation, Markdown upload and processing, local Ollama indexing, and saved RAG answer/citation display. Native platform configurations beyond the development Intel Mac still need clean-machine validation.

## Release blockers

- Validate native artifacts on clean Apple Silicon and Windows x64 machines; cross-compilation of the Python sidecar is not supported.
- Configure Apple Developer ID signing and notarization credentials. Ensure all nested PyInstaller native libraries are signed correctly; verify with Gatekeeper on a clean machine.
- Configure Windows code signing and verify installer/SmartScreen behavior.
- Review and distribute third-party license notices for Python/native dependencies, including PyMuPDF, before choosing an application license or publishing binaries. No repository-wide license is assumed by this migration.
- Test first-run Ollama installation instructions and downloads, disk-full/interrupted downloads, cached offline operation, and existing workspace migration on each platform.
- Manually compare workflows with the compatibility Flask app before removing it. Flask-specific multi-user admin, legacy global-index quiz/summarization and developer evaluation dashboards have not been ported as desktop screens. Exam-scoped oral practice, RAG and evaluation use their original domain services.

No signing secrets, updater keys, telemetry, cloud model fallback, model weights, or user databases belong in the bundle.

## Cleanup after manual acceptance

Candidates: `meditech_rag/app.py`, `meditech_rag/templates/`, `meditech_rag/assets/`, legacy `static/app.bundle.js`, `static/tailwind.css`, `static/app.css`, Docker packaging and the old `.command` installer. Keep the favicon as the desktop icon source. Existing Flask route tests must be migrated before deleting Flask; Python domain services and their tests remain shared.

### Learning dashboard and deadline planning

The Dashboard restores the Colloquily blue/violet identity and shows exam countdown,
practice completion, consecutive practice days, and fourteen days of activity.
Set an exam date, answers per question (default 3), and questions per session
(default 10). These settings persist per local learner and exam in SQLite.

The workload target includes accepted, enabled questions in enabled pools plus
accepted generated questions. Each question contributes at most the chosen number
of assessed answers. Pending, skipped, and needs-review evaluations do not count.
Remaining answers are distributed evenly over the days from today through the
exam date, including both. The dashboard shows the next fourteen days and adapts
when answers, question availability, or settings change. Past dates require a new
date; clearing the date removes the schedule. This is a practice-volume estimate,
not a prediction of passing or a mastery guarantee.

The question library offers a keyboard-accessible topic map, compact topic filters,
search, review-status filtering, and topic-specific practice. Map branches represent
topic membership, not inferred prerequisite relationships. Rings show average
assessed score, while readiness uses the existing evidence-based mastery rules.
The Progress page also includes topics that have not yet been practised.

### Simple learner flow

Create an exam with an optional date, upload lecture PDFs in Materials, then choose
**Prepare my practice**. Preparation runs in the backend even when navigating away:
text extraction and automatic quality checks → accepted-evidence index → five
starter questions. Newly generated questions pass evidence/rubric validation before
activation. Uncertain source passages and previously rejected/held questions are
not automatically approved. Existing practice questions are reused on retries.
Scanned PDFs without extractable text need text recognition before upload.

The main navigation focuses on Dashboard, Materials, Questions, Practice, Progress,
and Ask your materials. AI configuration, reported-question management, and the
legacy study-plan tools sit under Advanced tools. Manual source review and processing
are expandable controls on Materials. Practice uses defaults with optional session
customisation. Local AI setup is still required once; learners can create exams and
upload files before completing it. After an app restart, choose Prepare my practice
again if preparation was interrupted; ingestion reuses its saved checkpoints.

If the local model returns invalid question output or a request fails, preparation
falls back to up to five extractive starter questions. These ask the learner to
explain an accepted passage in their own words, with the exact passage as the
answer rubric. They do not add model-invented facts. Source links and normal
question validation still apply. The one-time AI screen offers a single action to
download the required models, with individual model controls under Model details.
