# Colloquily 0.1.1 — UX and learning-quality patch

This is the next patch after the published `v0.1.0-rc.4` preview. It does not
change the application identifier, persistent data locations, or schema version.
It is not a statement that a new public release has been published.

## Root causes

- Preparation requested only five questions, used the first 24 evidence units,
  and fell back to generic passage-quotation starter cards when generation failed.
- Generation checked JSON shape and exam-local citation IDs, but not whether
  the cited content actually supported the answer. Real testing also showed that
  the small model could incorrectly approve its own hallucinations.
- Skip was routed through a background AI model-answer job. It was not a direct
  session transition, and the frontend used the same asynchronous submission path.
- Evidence review exposed internal states and IDs. PDF page furniture, standalone
  headings, short fragments and slide structure could obscure useful content.
- AI readiness included global default models, rather than selecting suitable
  models for the current exam. Some exam-specific screens and practice history
  also retained state outside the selected exam.
- Passing previous questions as negative generation examples primed the small
  model to repeat a question from a different document. Empty schema-valid
  batches and large CPU response batches also obscured generation failures.

## Changes

- Searchable sidebar exam picker with active exam, optional date, practice counts,
  create action, keyboard focus/Escape handling and exam-specific state resets.
- Quiet system-font sidebar/toolbar, adaptive light/dark surfaces, responsive
  sizing, focus indicators, reduced-motion and contrast accommodations. The
  Apple design skill informed restraint, wayfinding, immediate feedback and
  separation of student workflows from Advanced tools. References:
  [Apple sidebars](https://developer.apple.com/design/human-interface-guidelines/sidebars),
  [toolbars](https://developer.apple.com/design/human-interface-guidelines/toolbars),
  [layout](https://developer.apple.com/design/human-interface-guidelines/layout).
- Automatic, exam-scoped Ollama preparation; resource/disk recommendations,
  installed-model reuse, preservation of explicit task/embedding settings,
  nonblocking download progress, cancellation and retry. Ollama itself is never
  installed automatically. Advanced local configuration remains available.
- All-document, topic/document-scoped evidence batches rather than a five-question
  exam cap. Preparation can be repeated to fill gaps without approving previously
  rejected or held questions. Coverage and validation reports are written atomically
  inside the exam's `reports/` directory.
- No passage-quotation fallback. Structured generation must provide exact source
  quotes for every answer point. Deterministic citation, quote, source-term,
  numeric, clarity and copied-fragment gates precede a local-model relevance/
  entailment check. Exact/near-text, embedding similarity and model-based semantic
  duplicate checks include previously reviewed questions.
  A new question cannot merely repackage facts already covered by another active
  question's answer rubric; stale historical questions do not satisfy this check.
- Generation uses source-only input and one candidate per request. Rejected
  targets rotate to another source fact, with bounded retries. Previous questions
  are not injected into generation; full-history deterministic/embedding checks
  still run, and only the independent audit receives a bounded duplicate hint.
  Interrogative boilerplate cannot disguise near-identical question wording.
- Skip is a separate synchronous API operation. It never calls an evaluator or
  model-answer generator. A persisted ungraded skipped attempt and session
  advance share one SQLite transaction. Expected-question IDs and serialized
  transitions make repeat requests idempotent. Skips do not inflate the session
  correctness percentage, and the last question completes the session.
  Answers also carry their question ID so a queued answer arriving after Skip
  cannot grade the next question. The additive API field remains optional for
  older integrations; the current desktop always sends it.
- Historical accepted questions with any stale source no longer count toward
  current topic coverage. Their review decisions/history remain stored.
- Student evidence states: Ready, Needs review, Unusable. Document summaries,
  source/page snippets, corrections, explicit review and reprocess actions are
  separate from raw metadata. Unusable content cannot be automatically approved.
- PDF counters/repeated edge text are filtered; nearby short PDF units are grouped
  without crossing page boundaries; section headings inform topic grouping.
  Broken mathematics/diagram-like fragments are retained for review rather than
  indiscriminately discarded. Extraction-failure reports are distinct from
  readable files/pages with no extractable text.

## Model policy

Default tiers use total RAM: below 12 GiB selects a lightweight 1.5B default;
12–23 GiB permits 4B; 24 GiB or more permits 8B. Compatible installed Qwen/ Phi-3
models fitting conservative size budgets are reused before downloading a default.
Explicit exam task settings take precedence. Available RAM further restricts the
installed-model size budget when it can be measured. The embedding model is retained
when already configured. Apple Silicon unified memory and NVIDIA driver-reported
VRAM are recorded where detectable, but GPU memory is not added to the RAM budget.

Threshold overrides: `COLLOQUILY_MEDIUM_MODEL_RAM_GB` and
`COLLOQUILY_LARGE_MODEL_RAM_GB`. Model storage discovery respects `OLLAMA_MODELS`;
the disk estimate includes a safety reserve and is conservative for custom models.
Model weights are not bundled; their separate upstream terms still apply.

Ollama stream semantics and cached-layer resumption follow the
[official API documentation](https://github.com/ollama/ollama/blob/main/docs/api.md).
Inference and embeddings remain local; downloading weights can use the internet.

## Verification

Local results (2026-10-17): 69 backend tests, 65 domain tests and 4 frontend
utility tests pass; translation key/interpolation parity and the TypeScript/Vite
production build pass. Intel macOS release compilation and `.app` bundling pass.
Frozen backend self-tests and the license inventory pass. Browser checks pass
for exam search/switching/material isolation, light/dark appearance, German
navigation and a 760-pixel-wide window. Synthetic PDF rendering was inspected.

Only a successful required real-model run for the release revision, followed by
source review, is sign-off evidence. The following earlier failures are retained
as diagnostic history, not passing acceptance:

An early
`qwen2.5:1.5b` run yielded only two qualifying questions; `phi3:mini` timed out
on CPU and was stopped, not reported as a pass. Revised retries later retained
five candidates across two documents and completed a three-question Skip session,
but manual review found misleading comparisons and an incomplete comparison
rubric among those candidates. New regression gates reject comparisons between
a category and its own example, unsupported context qualifiers and comparisons
whose expected points omit one side, regardless of the model's classification.
Those latest gates have automated regression coverage. A fresh 2026-10-16 run
retained only three questions, below the four-question acceptance minimum, and
reported partial coverage. It failed acceptance; the earlier five-candidate run
also remains invalid as final evidence. Subsequent changes explicitly guide
generation with uncovered source facts and complete comparison rubrics, without
templated fallback questions or relaxed gates. Those historical runs were not
release approval; they did not publish a new release or insert fallback filler.

RC tag publication now requires both the real-model synthetic acceptance job and
every native build to succeed. Failed quality checks cannot publish an unsigned
preview. Superseded PR workflows are cancelled automatically; tag builds are not.

An initial CPU-only Apple Silicon CI run of Qwen3 4B also returned no usable
candidates. Candidate batches could previously be empty schema-valid no-ops;
they now require a candidate attempt, while every existing approval/rejection
gate remains mandatory. Empty outputs fail schema validation and are audited.
The regression suite verifies that this never inserts an approved fallback.
The real-model CI workflow uses only synthetic materials and preserves its
validation audit for diagnosis. Normal per-request timeouts remain unchanged;
its total acceptance window permits multiple serial CPU requests.

The 4B synthetic acceptance job runs on a standard 16 GB Linux runner with
Ollama 0.33.0 installed from an official SHA-256-pinned archive in the temporary
CI directory. Virtual 7 GB Mac runners could not finish the first 4B request
within the unchanged application timeout and were not counted as passes.
See [GitHub runner resources](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
and [Ollama's manual Linux installation](https://docs.ollama.com/linux).
Inference stays on the runner's loopback interface, cloud inference is disabled,
and all input documents are freshly generated synthetic fixtures.

The native matrix now runs all domain regressions on Windows as well as macOS.
This exposed eight fixture-cleanup errors on Windows: SQLite transaction context
managers do not close connections. The fixtures now use explicit `closing()`;
the subsequent Windows domain suite passes. The
[full native matrix](https://github.com/artemkolokoltsev/colloquily/actions/runs/38906920356)
passes Windows, Intel macOS and Apple Silicon macOS and contains three installer
archives plus three license/source archives. Latest checks are tracked in
[PR #3](https://github.com/artemkolokoltsev/colloquily/pull/3).

The clean packaging environment passes a current `pip_audit` check, and
`npm audit --omit=dev --audit-level=high` reports zero vulnerabilities. The older
development virtualenv contains unused vulnerable packages and is not the frozen
installer environment. Do not substitute its installed package list for the
collected release inventory.

Reprocessing now retains citation IDs for unchanged units and preserves manual
review decisions. Superseded extraction rows are retained for history but excluded
from active evidence. Questions whose sources no longer resolve remain stored
with their review decisions intact, but are excluded from practice eligibility.

Run the automated checks:

```sh
.venv/bin/python -m unittest discover -s backend/tests -v
.venv/bin/python scripts/test_core.py
npm test
npm run build
cargo check --locked --manifest-path src-tauri/Cargo.toml
```

Opt-in real-model check (only fresh synthetic data; refuses any model download):

```sh
.venv/bin/python scripts/smoke_learning_quality.py
```

It processes a PDF and Markdown document, checks exam isolation and citations,
then completes a session using only Skip while asserting that no evaluator runs.
Its benchmark requires at least four accepted questions across the documents.
Every synthetic topic batch must contribute at least one question, and failed
preparation jobs cannot pass acceptance merely because partial results were saved.
Failure must be reported, not turned into a passing result by inserting filler.
Use `--lightweight` to explicitly test the limited-hardware recommendation tier.
Use `--model qwen3:4b` to select an already installed model explicitly for the
disposable exam. The smoke test refuses all model downloads; install the selected
model separately first. Reports include model choices, coverage and failure data.
Minimum candidate count is only a smoke check; manual pedagogical review is still
required, as the comparison failures above demonstrate. Partial coverage is
reported separately from operation completion; useful validated results remain
available for practice without pretending that all topics are covered.

## Remaining limits / release gates

- Local models remain fallible. Exact quotes and lexical guards are conservative,
  not a formal proof of entailment. Cross-language paraphrases and mathematical
  derivations can be rejected even when valid. Review remains available.
- Small models may fail to cover every topic or return fewer questions than the
  planning target. Preparation reports this explicitly and preserves valid results.
  A stronger installed model can be selected in Advanced settings.
- OCR, diagram interpretation and automatic reconstruction of complex mathematical
  layouts are not implemented. Such content stays out of automatic approval.
- The user's original 33-page presentation and 16-page script were not supplied;
  regression tests cover a 49-unit, two-document plan, not those specific files.
- Native installers now build on every supported target; clean-machine GUI
  installation and hardware behavior still need verification. Signing/notarization
  and updater-key requirements from the previous preview still apply.
- Do not tag/publish 0.1.1 as release-ready until the critical quality acceptance
  checks and native build checks have been reviewed. Existing RC4 assets are unchanged.
