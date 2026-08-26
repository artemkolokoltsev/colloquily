# Oral Exam Trainer

Reusable, completely local oral-exam preparation based on reviewed university course material. The original MediTech workflows remain available during migration, while new material is isolated into subject-specific workspaces and accepted-only FAISS indexes.

## Subject workflow

1. Create a subject under `/admin/subjects`.
2. Place nested Markdown or PDF material under `data/subjects/<slug>/raw/`, or use the non-overwriting upload form.
3. Run deterministic processing and optionally structured cleanup through the configured local LLM.
4. Review suspicious units and manually accept, quarantine, reject, or correct them.
5. Build the subject index. Only accepted, retrieval-enabled knowledge units are embedded.

The processor hashes every source, skips unchanged files, checkpoints every batch, and resumes interrupted work. Files under `raw/` are never rewritten. Manually accepted edits remain authoritative during later processing.

```text
data/subjects/<slug>/
├── raw/
├── preprocessing/
├── cleaned/
├── quarantined/
├── accepted/
├── reports/
├── exam_packs/
└── index/
```

SQLite migrations preserve existing requests, sources, quizzes, and attempts under the automatically created `MediTech` subject. No legacy runtime files are deleted.

## Dokumentation

Die ausfuehrliche Projektdokumentation liegt als statische HTML-Dokumentation im Repository:

```text
../docs/index.html
```

Die Datei kann direkt im Browser geoeffnet werden. Sie enthaelt Architektur, Workflows, Datenstruktur, Konfiguration, Evaluation, Betriebsnotizen und eine Projektstruktur-Uebersicht.

## Features

- Lokaler PDF-Upload und Speicherung unter `data/pdfs/`
- PDF-Parsing mit PyMuPDF und optionalem Marker-Backend
- Strukturierte Dokument-, Seiten-, Block-, Topic- und Chunk-Metadaten
- Austauschbare Chunking-Strategien: `page`, `word`, `paragraph`, `semantic`, `structure`
- FAISS-Vektorsuche mit lokalen SentenceTransformer-Embeddings oder LM Studio
- Optionales Metadata-Reranking nach Topic-, Intent-, Rollen- und Qualitaetssignalen
- LLM-Antworten ueber Ollama oder LM Studio
- Inline-Zitate wie `[Q1]` mit klickbarer Quellenvorschau
- Zusammenfassungen fuer einzelne Seiten oder Seitenbereiche
- Quizgenerierung und Quiz-Auswertung pro Benutzer
- Login, Benutzerverwaltung und Admin-Bereich
- Request-Historie, Feedback, Analytics und Evaluation
- Vorbereitete Indexprofile fuer vergleichbare Retrieval-Experimente
- Optionales Langtrace-Tracing und Feedback-Sync

## Quick Start

```bash
cd meditech_rag
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull phi3:mini
python app.py
```

Danach im Browser oeffnen:

```text
http://localhost:8000
```

Default-Login fuer lokale Entwicklung:

- Benutzername: `admin`
- Passwort: `admin`

Bitte das Passwort aendern, wenn die App laenger oder in einem geteilten Umfeld verwendet wird.

## Konfiguration

Zentrale Defaults stehen in [`config.py`](config.py). Die App laedt zusaetzlich Umgebungswerte aus `.env`, `.env.local`, `.env.langtrace` und `.env.langtrace.local` im Projekt- oder App-Verzeichnis.

Wichtige Einstellungen:

| Einstellung | Zweck |
| --- | --- |
| `HOST`, `PORT`, `DEBUG` | Flask-Server |
| `CHUNKING_STRATEGY` | Default-Chunker: `page`, `word`, `paragraph`, `semantic`, `structure` |
| `ACTIVE_INDEX_NAME` | Vorbereitetes Indexprofil aus `configs/index_profiles.json` |
| `EMBED_BACKEND` | `st` oder `lmstudio` |
| `ST_EMBED_MODEL` | SentenceTransformer-Modell |
| `ST_ALLOW_DOWNLOAD` | Erlaubt initialen Hugging-Face-Download |
| `LLM_BACKEND` | `ollama` oder `lmstudio` |
| `OLLAMA_LLM_MODEL` | Ollama-Modell, z. B. `phi3:mini` |
| `ENABLE_METADATA_RERANK` | Aktiviert heuristisches Reranking |
| `ENABLE_LANGTRACE`, `LANGTRACE_MODE` | Optionales Tracing |

Viele Runtime-Parameter koennen im Admin-Bereich unter `/admin/settings` angepasst werden. Fuer Parser-, Chunking-, Embedding- oder LLM-Wechsel sollte danach der Index neu aufgebaut werden.

## Architektur

```text
Browser UI
  |
  v
Flask routes in app.py
  |
  +-- services/database.py          SQLite users, requests, feedback, quizzes
  +-- services/rag_engine.py        RAG orchestration
        |
        +-- document_preprocessor.py
        +-- pdf_parsers/
        +-- chunking/
        +-- embeddings/
        +-- vector_store.py
        +-- prompt_builder.py
        +-- llm/
        +-- persistence.py
        +-- evaluator.py
        +-- analytics.py
```

Zentrale Module:

| Pfad | Aufgabe |
| --- | --- |
| [`app.py`](app.py) | Flask-App, Auth, Admin, Chat, Summary, Quiz, Feedback, Struktur-Endpunkte |
| [`config.py`](config.py) | Pfade, Modelle, Chunking, Langtrace, Evaluation und Topic-Vokabular |
| [`services/rag_engine.py`](services/rag_engine.py) | Index laden/aufbauen, Retrieval, Reranking, Prompts, Antworten, Summaries, Quiz |
| [`services/index_builder.py`](services/index_builder.py) | Aufbau vorbereiteter Indexprofile |
| [`services/document_preprocessor.py`](services/document_preprocessor.py) | Dokument-, Seiten-, Block- und SourceUnit-Erzeugung |
| [`services/pdf_parsers/`](services/pdf_parsers/) | PyMuPDF- und Marker-Parser |
| [`services/chunking/`](services/chunking/) | Chunking-Strategien |
| [`services/embeddings/`](services/embeddings/) | SentenceTransformer- und LM-Studio-Embeddings |
| [`services/llm/`](services/llm/) | Ollama- und LM-Studio-LLM-Clients |
| [`services/vector_store.py`](services/vector_store.py) | FAISS-Suche |
| [`services/persistence.py`](services/persistence.py) | JSON/FAISS-Persistenz |
| [`services/database.py`](services/database.py) | SQLite-Persistenz fuer Benutzer, Requests, Feedback und Quiz |
| [`services/evaluator.py`](services/evaluator.py) | Automatische Retrieval- und Groundedness-Heuristiken |
| [`services/langtrace_service.py`](services/langtrace_service.py) | Optionales Tracing |

## Daten Und Persistenz

Die App arbeitet lokal und legt Laufzeitdaten unter `data/` ab:

```text
data/
|-- app.db                         SQLite-Datenbank
|-- pdfs/                          Hochgeladene PDFs
|-- index/                         Aktiver Legacy-/Runtime-Index
|   |-- vectors.faiss
|   |-- chunks.json
|   |-- documents.json
|   |-- pages.json
|   |-- structure.json
|   |-- analytics.json
|   `-- request_history.json
|-- indexes/                       Vorbereitete Indexprofile
|-- cache/                         Modelle, extrahierte Seiten, Bildcache
`-- eval/                          Datasets, Metriken, Runs
```

Beim Start versucht `RAGEngine`, zuerst das aktive vorbereitete Indexprofil zu laden. Wenn dieses fehlt, faellt die App auf den Legacy-Index unter `data/index/` zurueck. Ein normaler Chat-Start baut den Index nicht automatisch neu auf; Reindexing erfolgt ueber Admin-UI oder Skripte.

## Indexing

PDFs koennen im Admin-Bereich unter `/admin/documents` hochgeladen und indexiert werden. Alternativ lassen sich vorbereitete Profile per Skript bauen:

```bash
cd meditech_rag
python scripts/prepare_indexes.py
```

Profile stehen in [`configs/index_profiles.json`](configs/index_profiles.json), z. B.:

- `baseline_page_minilm`
- `paragraph_overlap_mpnet`
- `final_paragraph_overlap_mpnet_rerank`

## App-Workflows

| Workflow | Route | Beschreibung |
| --- | --- | --- |
| Login | `/login` | Benutzer anmelden |
| Chat | `/ask` | Frage beantworten und Quellen anzeigen |
| Summary | `/summarize` | Dokumentseiten zusammenfassen |
| Quiz | `/quiz`, `/quiz/submit` | Quiz generieren und auswerten |
| Feedback | `/feedback` | Like/Dislike und Freitext speichern |
| Documents | `/admin/documents` | PDFs verwalten und Index neu bauen |
| Settings | `/admin/settings` | Runtime-Parameter setzen |
| Evaluation | `/admin/eval` | Metriken, Indexprofile, Langtrace-Test |
| Structure API | `/structure` | Wissensstruktur als JSON exportieren |
| Topics Debug | `/topics` | Topic- und Tagging-Debugansicht |

## Evaluation

Die Evaluation vergleicht Retrieval- und Antwortqualitaet anhand lokaler Datasets und Heuristiken.

```bash
cd meditech_rag
python scripts/eval_smoke.py
python scripts/eval_chunking.py
python scripts/eval_retrieval_profiles.py
python scripts/eval_answer_subset.py
python scripts/eval_report.py
```

Datasets liegen unter `data/eval/datasets/`, Metriken unter `data/eval/metrics/`, Runs unter `data/eval/runs/`.

Erfasste Signale umfassen unter anderem:

- `hit_at_k`
- `first_relevant_rank`
- `citation_page_accuracy`
- `duplicate_retrieval_ratio`
- Warnsignale fuer moegliche Ungroundedness
- Feedback-Scores

## Langtrace Optional

Self-hosted Langtrace kann ueber Docker Compose gestartet werden:

```bash
make langtrace-up
make langtrace-logs
make langtrace-down
```

Die Compose-Datei liegt im Projektroot als `docker-compose.langtrace.yml`. Die App liest `.env.langtrace` und `.env.langtrace.local`, wenn vorhanden.

## Entwicklung

```bash
cd meditech_rag
python app.py
```

Oder aus dem Projektroot:

```bash
make dev
```

Tests:

```bash
cd meditech_rag
python -m pytest
```

Falls `pytest` nicht installiert ist:

```bash
pip install pytest
```

## Hinweise

- Die Anwendung ist fuer lokale Entwicklung und Studium ausgelegt.
- PDFs, FAISS-Indizes, Modellcache und SQLite-Datenbank koennen gross werden und enthalten potenziell private Inhalte.
- `data/` sollte nicht ungeprueft geteilt werden.
- Der Default-Admin `admin/admin` ist nur fuer lokale Entwicklung gedacht.
