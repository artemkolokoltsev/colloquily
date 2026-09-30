# Desktop migration

Repository inspection: `meditech_rag/app.py` combines Jinja rendering, Flask sessions/authentication, upload handling, and orchestration. Most domain work already lives in `services`: exam-scoped SQLite repositories, immutable raw workspaces, durable page-checkpoint ingestion, accepted-only FAISS indexes, question pools, grounded evaluation, persisted timed exam runs, coverage and five-day plans. Preserve these modules and their tests.

The current model configuration is **qwen2.5:1.5b** for structured tasks, **phi3:mini** for oral answers, and **embeddinggemma:latest** for exam embeddings (not just phi3). Existing exams can override these settings. Data already supports COLLOQUILY_DATA_DIR. Legacy Flask uses admin/admin; the new local API needs no login but must reject foreign browser origins and use a desktop launch token.

Implementation order:
1. Add a FastAPI service adapter and typed API, retaining core imports and database schema. Add OS data paths; preserve repository data for browser development.
2. Build React workflows for exams, material processing/review, questions, assistant, practice/mocks, results, plans and settings. Poll durable ingestion jobs and background operation status.
3. Add Tauri v2 lifecycle and PyInstaller packaging. Use one loopback sidecar, readiness checks, startup errors and shutdown.
4. Add explicit model setup with real Ollama pull progress; retain configured task models and embeddings.
5. Verify existing tests, API smoke tests, TypeScript/Vite and native compilation. Keep legacy Flask files until parity is manually verified; document native build/signing status honestly.

Do not delete existing user work or move live SQLite files automatically. For migration, stop the old app and copy the whole data directory (including any WAL files), or use COLLOQUILY_DATA_DIR. Keep a backup.
