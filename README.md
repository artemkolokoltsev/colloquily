# MediTech RAG

MediTech RAG is a local Flask application for studying German medical technology lecture PDFs with retrieval-augmented generation. It stores uploaded PDFs locally, builds FAISS indexes, retrieves source-backed context, and provides question answering, summaries, quizzes, admin analytics, evaluation tooling, and optional Langtrace observability.

The main application lives in [`meditech_rag/`](meditech_rag/).

## Open The Documentation

Open the static project documentation in a browser:

```text
docs/index.html
```

The documentation page is self-contained enough to open directly from the filesystem and also uses browser documentation libraries for diagrams and code highlighting when internet access is available.

## Quick Start

```bash
cd meditech_rag
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull phi3:mini
python app.py
```

Then open `http://localhost:8000`.

Default local admin account:

- Username: `admin`
- Password: `admin`

Change the default password before using the app beyond local development.

## Useful Commands

```bash
make dev
make langtrace-up
make langtrace-logs
make langtrace-down
```

## Project Layout

```text
.
|-- docs/                         Static browser documentation
|-- docker/                       Langtrace database bootstrap files
|-- Literature/                   Research PDFs and references
|-- meditech_rag/                 Flask RAG application
|   |-- app.py                    Flask routes and UI workflow orchestration
|   |-- config.py                 Runtime defaults, paths, model settings
|   |-- configs/                  Prepared index profile definitions
|   |-- data/                     Local PDFs, indexes, cache, eval data, SQLite DB
|   |-- scripts/                  Index preparation and evaluation scripts
|   |-- services/                 RAG, parsing, indexing, persistence, eval services
|   |-- static/                   CSS
|   |-- templates/                Flask/Jinja pages
|   `-- tests/                    Focused tests
|-- docker-compose.langtrace.yml  Optional self-hosted Langtrace stack
|-- Makefile                      Convenience commands
`-- README.md                     Repository entry point
```

See [`meditech_rag/README.md`](meditech_rag/README.md) for the application-level guide.
