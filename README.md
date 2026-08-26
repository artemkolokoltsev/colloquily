# Oral Exam Trainer

Oral Exam Trainer is a reusable, completely local Flask application for preparing evidence-grounded university oral exams. It supports exam-isolated Markdown/PDF ingestion, quality review, accepted-only FAISS indexes, grounded questions and evaluation, timed single- and multi-exam practice, and a five-day study plan.

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
|-- meditech_rag/                 Oral Exam Trainer application (legacy folder name retained)
|   |-- app.py                    Flask routes and UI workflow orchestration
|   |-- config.py                 Runtime defaults, paths, model settings
|   |-- configs/                  Prepared index profile definitions
|   |-- data/exams/               Exam-isolated raw material, artifacts, and FAISS indexes
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
