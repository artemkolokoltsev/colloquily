# Colloquily 0.1.2 — UX, page notes and reliable learning progress

Candidate implementation prepared for gated publication as `v0.1.2-rc.1`. Remote tags were checked before selecting 0.1.2: the latest matching tag was `v0.1.1-rc.1`, with no `v0.1.2` tag.

## Root-cause audit

- **Topics:** PDF topic detection attached a heading only to the individual coherent text fragment containing it. Other fragments from the same slide lost the heading. Topic insertion compared exact names, creating case/punctuation variants. Generation inherited only the first evidence unit's topic. Question lists and practice filters preferred denormalized names over the actual topic relation. No conservative historical repair or manual assignment provenance existed.
- **Scores:** Home excluded skipped/pending attempts, while Progress averages included any numeric score. Topic mastery could also include skipped zeroes. Skips were stored with a null score and did not retain canonical answer points. Session percentages counted skips in their denominator, but this was not explained in the interface.
- **AI:** App initialization unconditionally submitted preparation whenever Ollama was running. The setup page compared global defaults and every exam's models, causing unrelated missing models to look like a current-exam setup requirement. A reusable installed recommendation needed to be persisted before reporting readiness.
- **Materials:** The screen listed filenames and evidence diagnostics without an integrated reader. It fetched all evidence, all question rubrics, and preparation state every 2.5 seconds even when idle.
- **Home:** Dashboard and Progress repeated metrics. The learning-plan form and knowledge map dominated the main view; historical feedback used a dense table with a raw JSON editor.

## Student navigation

- **Home:** selected exam, deadline, daily goal/completion, practiced/available questions, evaluated-answer average, activity and topic overview. Learning plan expands in place; detailed history opens from Home.
- **Materials:** document cards, processing state, page count, import date, local PDF reader and page notes. Preparation and evidence review are disclosures.
- **Practice:** answering remains primary; Manage Questions is secondary. Search, review/topic filters, expected points, lazy source citations, enable/disable, generation and manual topic assignment remain available.
- **Ask:** source-grounded questions, with an explicit unchecked option to include personal notes and distinct annotation citations.
- **Settings:** language, backups and updates; manual models and technical controls expand under Advanced tools.

Exam switching remains near the sidebar brand. Legacy internal page names and cross-page actions remain supported. Exam-bound content is remounted; prior AI status is cleared and its polling is aborted on switching.

## Changes by feature

### PDF library and notes

PDF.js and its worker, compatibility polyfills, fonts, character maps and WASM assets are bundled locally. No online viewer or runtime CDN is used. The reader supports previous/next/page selection, zoom, fit-width, bounded sequential text search, remembered page and note-page indicators. Reader code loads on demand.

Notes use stable document IDs and positive PDF page numbers. The API validates exam ownership and actual page bounds. Saves are debounced and serialized, errors are visible, navigation flushes pending edits, and a local recovery draft survives an interrupted save. SQLite is authoritative after a successful save. Source PDFs are opened read-only and never rewritten.

Personal annotations do not enter accepted lecture evidence or FAISS. Ask includes them only on explicit opt-in, using bounded lexical retrieval and `N<document>_<page>` citations, marked STUDENT ANNOTATION. They are not used for automatic question generation.

### Topic integrity

A clear slide heading propagates to that page's body fragments. Normalized case/punctuation matching reuses topics. Question creation validates exam ownership and classifies from accepted evidence or a unique existing topic name. Conflicting/unsupported cases stay unassigned.

Manage Questions permits manual reassignment. Advanced tools can start an idempotent background reclassification job. It recovers unambiguous evidence headings, changes only unassigned questions and skips manual assignments, including explicit manual unassignment. It returns unresolved IDs/reasons. It never removes answers or source references.

### Honest progress and feedback

Skipped attempts earn zero, bypass the evaluator and show canonical expected points without AI reasoning. Historical skipped records are normalized for presentation without rewriting saved evaluations or correction records.

Home averages, Progress averages and topic mastery use evaluated attempts only. Session percentages include evaluated attempts and skipped questions in the possible-points denominator; pending attempts remain provisional. Daily allocations account for today's completed repetitions so a finished daily goal stays complete.

Answer history uses expandable review cards with earned/max points, descriptive score states, expected points, the student's answer and available citations. Older answers load in bounded cursor pages. Score colors progress from red through amber to green; numbers and labels remain visible. Raw correction JSON is removed from the default UI; existing correction provenance stays intact in SQLite.

### AI and performance

Exam readiness reports ready/preparing/Ollama-unavailable/insufficient-storage/failed states; the client starts in checking. Ready compatible models are reused without a preparation job or banner. Missing models use the existing device-aware policy. Failed preparation requires a retry. Automatic and advanced manual downloads share a lock; repeated requests for one exam share a job. Preparation for another exam recomputes the installed-model plan after acquiring the lock.

Materials polls only while work runs and loads evidence/questions only for advanced review. Home uses compact question/attempt/evidence projections rather than loading full answers and rubrics. The exam picker uses compact SQL summaries.

## Forward migration and preservation

Schema **10 → 11** adds:

- `document_page_notes(document_id, page, content, updated_at)` with a composite primary key and document foreign key.
- `question_topic_assignments(question_id, provenance)` to protect manual assignments and unassignments.

The existing migration mechanism takes a validated SQLite backup before upgrading, rejects newer schemas, performs transactional initialization and checks integrity. Existing exams, PDFs, questions, evidence IDs, answers, correction records, histories, indexes and settings are retained. The application identifier remains `org.colloquily.desktop`; persistent data paths and updater architecture are unchanged. Tests and browser checks used disposable directories only.

## Verification

Actual results on Intel macOS:

- Backend/API: **84 passed**, including 13 redesign regressions and the daily-goal regression.
- Core Python: **65 passed**.
- Frontend: **4 existing tests passed**; English/German catalog and interpolation checks passed.
- TypeScript/Vite production build: passed; advisory lazy PDF chunk-size warning only.
- Rust `cargo check --locked`: passed.
- Clean release-environment sidecar build and frozen self-test: passed.
- Frozen sidecar lifecycle smoke: passed (loopback health, token/origin checks, parent EOF shutdown).
- Tauri unsigned Intel macOS release `.app` and updater archive: built successfully locally. The RC workflow builds the distributable installers before publication.
- Browser: PDF render/navigation/search/notes/reopen/restart, exam-note isolation, 800px layout, dark/reduced-motion, German/English switching, and skipped expected-point review checked against a synthetic workspace.

See `output/verification/` for captured command logs and `output/playwright/redesign/` for screenshots. Regression coverage includes PDF source bytes/page bounds/special filenames, note create/edit/reopen/restart, exam isolation, normalized topic assignment and filtering, manual assignment protection, answer preservation, ambiguous classifications, concurrent document identity, skipped averages/mastery, daily-goal completion, cursor history, annotation provenance and shared-model download serialization.

## Release constraints

- Local verification covers this Intel macOS host. Apple Silicon and Windows native builds remain CI gates.
- The app bundle is unsigned and not notarized. Updater signing credentials/public-key configuration remain required for publication.
- Live model downloads and subjective answer quality were not exercised; model policy and concurrency were tested with controlled providers.
- Image-only PDFs still need OCR outside this release. PDF text search depends on an extractable text layer. Page notes are text only.
- Annotation retrieval is bounded lexical matching, not a second vector index. It is available in Ask, not automatic question generation.
- PDF compatibility polyfills add a lazy chunk above Vite's advisory 500 kB threshold; it is fetched only when opening the reader.


## Design references

The implementation applies the local Apple design skill and Apple’s [sidebar](https://developer.apple.com/design/human-interface-guidelines/sidebars), [layout](https://developer.apple.com/design/human-interface-guidelines/layout), and [Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/). The reader follows the maintained [PDF.js library examples](https://mozilla.github.io/pdf.js/examples/index.html), with all runtime assets bundled locally.
