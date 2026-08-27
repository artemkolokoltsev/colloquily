# Colloquily

Colloquily is a reusable, completely local Flask application for preparing evidence-grounded university oral exams. It supports exam-isolated Markdown/PDF ingestion, quality review, accepted-only FAISS indexes, grounded questions and evaluation, timed single- and multi-exam practice, and a five-day study plan.

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

## Run and test

Ollama must be running before starting Colloquily. From the repository root:

```bash
ollama list
make dev
```

Open `http://localhost:8000` and sign in with `admin` / `admin` for local development.
Run the automated checks in a second terminal:

```bash
make test
make verify
```

The first command runs the unit and integration suite. The second creates disposable PDF and Markdown exams and verifies ingestion, exam isolation, evaluation, mock-exam state, and index reload.

## Install on macOS with Docker

Start Docker Desktop and Ollama, then double-click `Install Colloquily.command`. It builds a local application image, starts Colloquily in a container, and opens `http://localhost:8000`. Application code runs inside the image; durable exam data stays in `meditech_rag/data` on the Mac.

From Terminal, the equivalent commands are:

```bash
docker compose up -d --build
open http://localhost:8000
```

Stop it with `docker compose down`. Ollama remains private on the Mac and is reached from the container through `host.docker.internal`.

## Useful Commands

```bash
make dev
make test
make verify
```

## Project Layout

```text
.
|-- docs/                         Static browser documentation
|-- Literature/                   Research PDFs and references
|-- meditech_rag/                 Colloquily application (package path retained for compatibility)
|   |-- app.py                    Flask routes and UI workflow orchestration
|   |-- config.py                 Runtime defaults, paths, model settings
|   |-- configs/                  Prepared index profile definitions
|   |-- data/exams/               Exam-isolated raw material, artifacts, and FAISS indexes
|   |-- data/colloquily.db        Durable SQLite database (WAL, full synchronous writes)
|   |-- scripts/                  Index preparation and evaluation scripts
|   |-- services/                 RAG, parsing, indexing, persistence, eval services
|   |-- static/                   CSS
|   |-- templates/                Flask/Jinja pages
|   `-- tests/                    Focused tests
|-- Makefile                      Convenience commands
`-- README.md                     Repository entry point
```

See [`meditech_rag/README.md`](meditech_rag/README.md) for the application-level guide.
