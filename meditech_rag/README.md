> **Compatibility application:** This guide describes the retained Flask application. For the React/FastAPI/Tauri architecture, current development and desktop builds, see the [root README](../README.md). Docker and the old installer below are legacy developer options.

# Colloquily

Colloquily is a completely local, English-language study workspace for evidence-grounded university oral-exam preparation. It uses typed text only. Course data, prompts, models, indexes, attempts, and evaluations remain on the local machine.

## Run locally

From this directory:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull phi3:mini
python app.py
```

Open `http://localhost:8000` to start directly—no login is needed. Use Advanced settings to experiment with parsing, chunking, retrieval, and local models.

From the repository root, `make dev`, `make test`, and `make verify` provide the same development workflow. Run `npm install && npm run build` after changing Tailwind, Alpine, Lucide, or UI templates.

## Run as an installed Docker application

Start Docker Desktop and Ollama, then double-click `Install Colloquily.command`, or run:

```bash
docker compose up -d --build
```

The application runs from the Docker image at `http://localhost:8000`. Durable exam data is mounted at `data/`; Ollama is reached privately through `host.docker.internal`.

## Exam workflow

1. Create an exam under **Exams & Review**.
2. Add English PDF or Markdown course sources. Each exam uses an isolated `data/exams/<slug>/` workspace.
3. Process material in Fast, Deep, or Deterministic mode. Jobs checkpoint each PDF page and can resume after an interruption.
4. Review uncertain evidence. Raw source files are never rewritten.
5. Build the accepted-evidence index.
6. Study, practise accepted questions, run timed mock exams, and use the study plan.

Every Study question and grounded answer is stored under `/history` with its citations and local-model metadata. Each Ask request also creates its own `user_question` card with **Needs review** status under **Exams & Review → Questions**. Existing Ask history is backfilled during the database migration.

Reported Colloquium questions can be imported under **Exams & Review → Reported questions** and converted into evidence-grounded cards. Their exact reported wording and follow-up-chain provenance remain immutable; current accepted course evidence supplies a draft rubric. Cards must still be reviewed and accepted before entering a mock exam. The same Questions screen can extend the pool with additional course-derived questions.

The Trainer provides a single-exam **15-minute mock** and a **Complete Colloquium** consisting of exactly three separate 15-minute exams. The complete run shows readiness for all three question pools, preserves separate timers and scores, and requires an explicit transition between exams.

A 15-minute mock plans six grounded questions by default (about 2½ minutes each). Accepted cards are preferred; evidence-grounded cards awaiting review may fill a thin practice pool and remain visibly reviewable.

Timed mocks only collect answers while the clock is running. **Skip question** records an omission and advances without a model call. After the run, **Evaluate stored answers** produces the score, missing points, and improved oral answer for each response. Question History provides an exam-filtered, scrollable question list with a selected answer and evidence preview.

German grading uses 4.0 at 50% and 5.0 below 50%. A complete multi-exam Colloquium passes only when every selected exam reaches 50%; its overall grade is then the median of the individual German grades.

CPU defaults route structured tasks to local `qwen2.5:1.5b` (2048 context, 180 output tokens) and oral answers to `phi3:mini` (3072 context, 320 output tokens). LLM responses and Ollama embeddings use persistent content/configuration caches. Measured Intel Mac results are stored under `data/eval/benchmarks/` and runtime metrics appear under **Admin → Local evaluation**.

Only accepted, retrieval-enabled knowledge units enter an exam index. Question and answer generation rejects unresolved evidence identifiers.

## Curated question pools

Open **Exams & Review → Questions** for an exam to import reusable curated question pools. Colloquily accepts `.json`, `.jsonl`, `.md`, and `.markdown`, normalizes every format into the existing question model, and previews topic/priority counts, validation errors, and duplicates before confirmation. Importing never calls a model or rewrites curated wording and answer points.

JSON accepts either an array or `{ "questions": [...] }`. Aliases include `question`/`text`, `topic`/`category`, `expected_answer_points`/`answer_points`, and `possible_followups`/`followups`. Markdown uses course-independent `# Topic` and `## ID — Question` headings with optional metadata, answer-point bullets, and follow-up bullets.

Duplicates are skipped first by external ID within the exam, then by normalized question text. A confirmed pool is stored in one SQLite transaction. Questions can be filtered, enabled/disabled, deleted individually, or removed with the complete pool. Random practice balances selection across topics and deprioritizes recently answered questions.

Schema migration 9 runs automatically at startup; no separate migration command is needed. Restart the app or container after updating.

Every submitted learning action shows task-specific in-context progress and
elapsed time while local retrieval, generation, evaluation, or indexing is
running. Duplicate submissions are blocked, and reduced-motion preferences
receive a static progress treatment.

## Coverage terminology

Colloquily keeps two dimensions separate everywhere in the UI.

### Material coverage

Material coverage describes whether accepted course evidence supports an exam-ready explanation of a topic. It does not measure the learner.

The previous implementation used this exact calculation:

```text
if conflict_count > 0: conflicting
else if accepted_unit_count >= 3: strong
else if accepted_unit_count > 0: weak
else: none
```

That calculation was misleading because raw volume alone could make a topic appear ready, and `Unassigned` could become `strong`. It has been removed.

The current calculation normalizes topic headings, then checks meaningful evidence dimensions:

- definition or central explanation;
- core mechanism;
- model components when applicable;
- relationships or process when applicable;
- example or application;
- limitation or comparison when applicable;
- reliable source traceability;
- absence of unresolved conflicts.

The material states are:

- **Complete** — accepted, traceable evidence covers every required dimension.
- **Partial** — usable accepted evidence exists, but required dimensions are missing.
- **Missing** — no usable accepted evidence exists.
- **Needs review** — relevant evidence exists but remains uncertain.
- **Conflicting** — accepted evidence contains an unresolved source conflict.
- **Unassigned** — material has no reliable normalized topic mapping. It can never be Complete, regardless of unit count.

The applicable dimension set is explicit: every topic requires a central explanation, mechanism, application/example, and traceability. Model/framework topics also require components; process/workflow topics require relationships/process; and comparison/evaluation topics require limitations/comparisons.

### Learner mastery

Learner mastery describes answered-question performance and never derives from material count. Its states are:

- **Not practised** — no answered questions exist for the topic.
- **Learning** — practice exists but exam-ready criteria are not yet met.
- **Weak** — average correctness is below 2.5/5 or repeated omissions/incorrect points exceed one per attempt.
- **Exam-ready** — repeated recent answers average at least 4/5, the latest answer is at least 4/5, omissions are rare, average time is within 120% of the target, and performance is supported by either a successful mock or at least three attempts.

The UI tooltip for each topic reports accepted evidence count, covered and missing dimensions, review and conflict counts, and practice evidence.

## Topic normalization

Before coverage is calculated, Colloquily removes slide/page number prefixes, ignores number-only headings, merges identical normalized titles, combines repeated sequential headings, and splits short concatenated heading lines. Original source titles remain attached for traceability. Uncertain or meaningless titles move to **Unassigned**.

## Durable processing and storage

```text
data/
├── colloquily.db
└── exams/<exam-slug>/
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

SQLite uses WAL and full synchronous writes. Processing hashes every source, skips unchanged files, checkpoints batches, records failures, and supports retry from the last durable checkpoint.

Repeated PDF headers and footers are detected across page boundaries. A unit
containing only repeated page furniture is automatically rejected; when a unit
also contains valid academic body text, Colloquily removes the repeated line
and automatically accepts the clean remainder when all other quality checks
pass. Icon-font glyphs, slide-number prefixes, duplicate titles, generic
fragments, and ambiguous concatenated headings are removed from topic mappings;
uncertain mappings remain Unassigned and original text stays in source records.

## Tests

```bash
python -m unittest discover -s tests -v
python scripts/verify_five_day_mvp.py
```

The suite includes explicit coverage regressions proving that 1,494 Unassigned units never become Complete, count alone cannot create Complete coverage, numbered slide headings merge, a few complete high-quality evidence units can be Complete, and mastery remains Not practised until a learner answers a question.
