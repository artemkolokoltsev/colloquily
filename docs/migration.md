# Desktop architecture

Colloquily has a single application: React in Tauri, backed by a loopback FastAPI sidecar.

- `frontend/`: desktop screens, localization, typed API client.
- `backend/api/`, `backend/services/`: API and workflow adapters.
- `backend/core/`: exam-scoped ingestion, PDFium parsing, SQLite, FAISS retrieval, evaluation.
- `tests/core/`, `backend/tests/`, `tests/frontend/`: isolated regression suites.
- `scripts/`: build, notices, verification; `scripts/developer/`: supported development checks.
- `data/`: ignored personal workspace, never bundled.

The Flask interface, global-index RAG engine, obsolete benchmark pipelines, Docker packaging and old installer were removed. Current PDF and document-import regressions remain; route coverage targets FastAPI and pagination/source-page coverage targets the React utilities.

Existing database migrations and saved-setting normalization remain because they protect user data, not because a second application is supported. Inference uses locally installed Ollama or LM Studio. The packaged API requires a launch token and rejects foreign browser origins.
