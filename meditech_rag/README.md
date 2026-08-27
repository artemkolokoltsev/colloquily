# Colloquily

Reusable, completely local oral-exam preparation based on reviewed university course material. Each exam is isolated in its own workspace and accepted-only FAISS index.

## Exam workflow

1. Create an exam under `/admin/subjects` (the legacy URL remains stable).
2. Place nested Markdown or PDF material under `data/exams/<exam-slug>/raw/`, or use the non-overwriting upload form.
3. Use **Fast** cleanup by default (local LLM only for suspicious sections), **Deep** for every section, or deterministic mode for troubleshooting.
4. Review suspicious units and manually accept, quarantine, reject, or correct them.
5. Build the exam index. Only accepted, retrieval-enabled knowledge units are embedded.
6. Open the **5-Day Plan** for a ranked answer to “What should I study now?”, then practice due/weak questions.

The processor hashes every source, skips unchanged files, checkpoints every batch, and resumes interrupted work. Files under `raw/` are never rewritten. Manually accepted edits remain authoritative during later processing.

PDF processing runs as a durable background job with one checkpoint per page. The Exams page polls the persisted job state and displays document/page progress. **Resume / retry from checkpoint** continues an interrupted job after a server restart. Fast cleanup is opportunistic: if the local model times out or returns malformed structured output, Colloquily keeps deterministic review candidates and finishes the corpus instead of discarding the job.

```text
data/exams/<exam-slug>/
├── raw/
├── extracted/
├── preprocessing/
├── cleaned/
├── quarantined/
├── accepted/
├── reports/
├── exam_packs/
└── index/
```

SQLite migrations preserve existing requests, sources, quizzes, and attempts under a neutral imported-exam record. No existing learning data is deleted.

## Training workflow

- `/trainer` provides single-question, weak-topic, 30/60/90-second rapid practice, full exam simulations, and separate-session multi-exam tests.
- `/exams/<exam-id>/five-day` combines accepted learning cards, coverage, scores, omissions, timing, recency, and remaining days into a ranked study plan.
- `/progress/<subject-id>` shows score and response-time trends, missing core points, misconceptions, weak topics, mock history, and spaced-repetition priorities.
- Generated questions, evaluations, follow-ups, and exam packs are rejected when evidence IDs do not resolve to accepted units in the active subject.
- Manual knowledge edits and corrected evaluations are persisted as authoritative review/audit records.

## Local model verification

Model roles are configured separately per exam under **Exams → Local models**. Ollama and LM Studio are supported for cleaning, topic extraction, question generation, answering, evaluation, and examiner follow-ups. Local Ollama `embeddinggemma:latest` is the default exam embedding backend; SentenceTransformer and LM Studio remain optional.

Run the disposable local-model smoke test with:

```bash
python3.11 scripts/smoke_oral_exam_trainer.py
python3.11 scripts/verify_five_day_mvp.py
```

The first command validates an actual Ollama cleanup response and raw-file immutability. The second creates nested PDF and Markdown exams, then verifies ingestion, isolation, grounded question/evaluation, a short mock, the five-day recommender, and index persistence across reload.

## Known limitations

- Training uses typed text input only; microphone recording and speech-to-text are not part of Colloquily.
- Adaptive simulation follow-ups are selected from the reviewed subject question pool. The system does not risk an unvalidated dynamic question when no grounded follow-up is available.
- The Python package directory keeps its historical path only for import and migration compatibility; all product surfaces and prompts are branded Colloquily.
- Imported PDF summary and multiple-choice routes remain available for older data, while new exams use the stricter accepted-evidence workflows.

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
- FAISS-Vektorsuche mit Ollama EmbeddingGemma, SentenceTransformer oder LM Studio
- Optionales Metadata-Reranking nach Topic-, Intent-, Rollen- und Qualitaetssignalen
- LLM-Antworten ueber Ollama oder LM Studio
- Inline-Zitate wie `[Q1]` mit klickbarer Quellenvorschau
- Zusammenfassungen fuer einzelne Seiten oder Seitenbereiche
- Quizgenerierung und Quiz-Auswertung pro Benutzer
- Login, Benutzerverwaltung und Admin-Bereich
- Request-Historie, Feedback, Analytics und Evaluation
- Vorbereitete Indexprofile fuer vergleichbare Retrieval-Experimente
- Lokale Evaluation ohne externe Telemetrie

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

Zentrale Defaults stehen in [`config.py`](config.py). Die App laedt zusaetzlich Umgebungswerte aus `.env` und `.env.local` im Projekt- oder App-Verzeichnis.

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
| [`config.py`](config.py) | Pfade, Modelle, Chunking und lokale Evaluation |
| [`services/rag_engine.py`](services/rag_engine.py) | Index laden/aufbauen, Retrieval, Reranking, Prompts, Antworten, Summaries, Quiz |
| [`services/index_builder.py`](services/index_builder.py) | Aufbau vorbereiteter Indexprofile |
| [`services/document_preprocessor.py`](services/document_preprocessor.py) | Dokument-, Seiten-, Block- und SourceUnit-Erzeugung |
| [`services/pdf_parsers/`](services/pdf_parsers/) | PyMuPDF- und Marker-Parser |
| [`services/chunking/`](services/chunking/) | Chunking-Strategien |
| [`services/embeddings/`](services/embeddings/) | Ollama-, SentenceTransformer- und LM-Studio-Embeddings |
| [`services/llm/`](services/llm/) | Ollama- und LM-Studio-LLM-Clients |
| [`services/vector_store.py`](services/vector_store.py) | FAISS-Suche |
| [`services/persistence.py`](services/persistence.py) | JSON/FAISS-Persistenz |
| [`services/database.py`](services/database.py) | SQLite-Persistenz fuer Benutzer, Requests, Feedback und Quiz |
| [`services/evaluator.py`](services/evaluator.py) | Automatische Retrieval- und Groundedness-Heuristiken |

## Daten Und Persistenz

Die App arbeitet lokal und legt Laufzeitdaten unter `data/` ab:

```text
data/
|-- colloquily.db                  Durable SQLite-Datenbank (WAL + FULL synchronous)
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
| Evaluation | `/admin/eval` | Lokale Metriken, Datensaetze und Indexprofile |
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
