# Colloquily

Colloquily helps you prepare for university oral exams using your own course material. Create an exam, set its date, upload your lecture PDFs, and choose **Prepare my practice**. Colloquily checks the study text and prepares source-grounded questions so you can start practising without managing indexes or review queues.

Your dashboard shows a daily practice plan, topic progress, and activity. Processing, source review, question management, and model configuration remain available under **Advanced tools** or expandable options.

Documents, indexes, answers, and evaluations stay on your computer. There is no analytics service, cloud account, or cloud LLM fallback. Internet access is needed to install the application and explicitly download AI models; inference uses local Ollama (existing LM Studio configurations remain supported by the Python core).

## Desktop installation

The desktop migration is under development. **Signed public installers are not yet published.** Packaging is configured for macOS 14+ on Apple Silicon and Intel, and Windows x64. An unsigned Intel macOS debug application has been built and launch-tested. Apple Silicon and Windows builds still require native validation; signing/notarization requires release credentials.

A desktop release contains the React UI, Tauri application, Python runtime, FastAPI backend, and native Python dependencies. End users will not need Python, Node.js, Docker, or a terminal. Install the macOS application or Windows installer, open Colloquily, and follow **AI setup**. The backend starts and stops with the desktop application.

Ollama is a separate installation for now. Install it from [Ollama](https://ollama.com/download), open it, then click **Check again** in Colloquily. Download buttons display actual Ollama download progress and failures. Model weights are not embedded in the installer or downloaded without an explicit action.

The existing defaults are:

- `qwen2.5:1.5b` for structured tasks and evaluation;
- `phi3:mini` for oral answers;
- `embeddinggemma:latest` for exam embeddings.

Setup also checks models configured for individual exams. Retry interrupted downloads to reuse Ollama's cached layers. Keep enough free space for all models; Ollama's disk and network errors are shown in the app.

## Architecture

```text
React + TypeScript (Vite) → HTTP API → FastAPI
                                      ↓
                        existing Python domain services
                                      ↓
                          SQLite / FAISS / files / Ollama

Tauri v2 → bundled PyInstaller backend → loopback-only listener
```

The frontend contains presentation and API calls, not RAG or persistence logic. FastAPI adapters reuse `meditech_rag/services/` and the existing database schema. Ingestion retains durable checkpoints; indexing, generation, evaluation, and downloads run as background operations with status polling. Other operation handles are process-local: after a restart, retry the action; completed exam attempts and evaluations remain in SQLite.

The desktop uses a random loopback port and a per-launch API token. Foreign browser origins are rejected. Both the desktop and browser applications open without a login. Existing owner records are reused to preserve progress; new databases use a local identity with a random unused password. Advanced settings provide parsing, chunking, retrieval, and model controls for RAG experiments.

## Development

Requirements: Python 3.11, Node.js 22+, and Ollama for inference. Desktop development additionally needs Rust (pinned in `rust-toolchain.toml`) and the [Tauri platform prerequisites](https://v2.tauri.app/start/prerequisites/), including Xcode Command Line Tools on macOS or Microsoft C++ Build Tools/WebView2 on Windows.

macOS shell:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
npm ci
npm run dev:all
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
npm ci
npm run dev:all
```

Browser development runs at `http://127.0.0.1:5173`; Vite proxies `/api` to the loopback backend on port 8765. `make dev` is equivalent on systems with Make. To run the processes separately:

```bash
npm run dev:backend
# In another terminal, with the virtual environment active:
npm run dev
```

FastAPI's interactive API reference is at `http://127.0.0.1:8765/docs` in browser development. Do not run multiple API workers against one data directory. The launcher fixes the bind address to loopback.

## Desktop development and builds

Activate the Python environment first. Build the backend on the **same OS and CPU architecture** as the desktop target; PyInstaller does not cross-compile.

```bash
npm run build:sidecar
npm run tauri -- dev
```

Tauri development launches its own sidecar. Stop `dev:all` first; Tauri starts Vite itself. Rebuild the sidecar after Python changes. Browser mode is faster for routine backend development.

macOS Apple Silicon, from a native ARM Python/Rust environment:

```bash
npm run build:sidecar
npm run tauri -- build --target aarch64-apple-darwin --bundles app,dmg
```

macOS Intel, from a native Intel Python/Rust environment:

```bash
npm run build:sidecar
npm run tauri -- build --target x86_64-apple-darwin --bundles app,dmg
```

Windows x64, from an x64 Python/Rust environment:

```powershell
npm run build:sidecar
npm run tauri -- build --target x86_64-pc-windows-msvc --bundles nsis
```

The script rejects mismatched Python/Rust architectures and writes the target-suffixed executable into `src-tauri/binaries/`. Installers appear under `src-tauri/target/<target>/release/bundle/`. There are no bundled LLM weights, though native Python/ML libraries can make the application sizable. See [desktop packaging](docs/desktop.md) for validation and signing requirements.

## Data and migration

Mutable files always live outside the installed application:

| Mode | Directory |
| --- | --- |
| Browser development | `meditech_rag/data/` (compatible with existing data) |
| macOS desktop | `~/Library/Application Support/Colloquily/` |
| Windows desktop | `%APPDATA%/Colloquily/` |
| Explicit override | `COLLOQUILY_DATA_DIR` |

The directory contains `colloquily.db`, `exams/`, model/processing caches, indexes, and saved settings. Application resources and prompts are read-only bundle content. To migrate an existing workspace, stop the old application, back up and copy the **whole data directory** to the desktop location. Do not copy a live SQLite database without its WAL. Colloquily does not silently relocate or delete existing data.

## Checks

With the Python environment active:

```bash
python scripts/test_core.py
python -m unittest discover -s backend/tests -v
npm run build
cargo check --manifest-path src-tauri/Cargo.toml
```

`make test` runs both Python suites. Native checking requires the generated sidecar and icons. The original integration verifier is available with `make verify` and requires configured local inference models. Architecture smoke tests use disposable data and mock model availability; they do not download models.

## Repository layout

```text
frontend/                 React screens, reusable components, typed API client
backend/api/              FastAPI routes
backend/models/           Pydantic API contracts
backend/services/         Workflow adapters, background jobs, LLM setup provider
backend/main.py           Local API lifecycle and access controls
backend/launcher.py       Loopback sidecar entry point
src-tauri/                Desktop lifecycle, capabilities, packaging and icons
scripts/                  Native sidecar build and isolated test runner
meditech_rag/services/     Preserved Python RAG, ingestion, evaluation and storage
meditech_rag/app_paths.py  Packaged/development data location resolution
meditech_rag/tests/        Existing regression suite
meditech_rag/app.py        Temporary Flask compatibility application
docs/                     Architecture, migration and packaging notes
```

The old Flask templates, Alpine/Tailwind assets, Docker files and `Install Colloquily.command` remain for compatibility and comparison while manual workflow parity is validated. They are not used by the desktop build. `make legacy-dev` and `npm run build:legacy` explicitly target that application. The old static `docs/index.html` describes the Flask-era application; use this README and the new migration/desktop notes for the current architecture.
