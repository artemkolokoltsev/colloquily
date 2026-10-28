# Engineering baseline and specification review

Observed on **2026-10-28**, starting from `release/0.1.9` at version 0.1.9. This change is on `docs/ui-practice-engineering`. Results below are local observations, not a claim that a new GitHub workflow or release has passed.

## Scope and documentation contracts

The immediate request is to refresh README UI references, explain the practice modes, and assess the attached engineering specification. This change implements that documentation work and establishes the requested baseline. Runtime refactoring, a new component-test stack and lint migration remain separate work, with concrete acceptance criteria below.

[PR #4](https://github.com/artemkolokoltsev/colloquily/pull/4) was an open draft when checked. Its nine new documentation/contract files were copied from commit `7334c36f2ec107de56ae023e7edaa8c35be3075a` onto this branch. Its README edit was incorporated into the refreshed README. The PR was not merged and `main` was not modified. Version and signing descriptions in the imported architecture document were updated against current source and release docs.

## Observed checks

Commands used the existing `.venv` with Python 3.11, Node 23.11.0 and the pinned Rust 1.90.0 toolchain. CI specifies Node 22, so this is not a fresh CI-environment reproduction. Python test suites use temporary workspaces and synthetic inputs.

| Check | Actual result |
| --- | --- |
| `npm test` | Passed: version consistency, translation parity and 17 frontend utility tests |
| `.venv/bin/python scripts/test_core.py` | Passed: 65 domain tests |
| `.venv/bin/python -m unittest discover -s backend/tests -v` | Passed: 124 backend/API tests |
| `npm run build` | Passed: strict TypeScript checking and Vite production bundle; Vite warns about chunks larger than 500 kB |
| `node scripts/smoke_pdf_reader.mjs` after the production build | Passed in Chromium and WebKit with synthetic HTTP fixtures and desktop CSP; local-server binding required execution outside the sandbox |
| `cargo check --locked --manifest-path src-tauri/Cargo.toml` | Passed using existing local native build prerequisites/artifacts |
| `cargo fmt --all --manifest-path src-tauri/Cargo.toml -- --check` | Could not run: `rustfmt` is not installed for the pinned toolchain |
| `cargo clippy --locked --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings` | Could not run: `clippy` is not installed for the pinned toolchain |
| Ruff / Python type checking | No repository configuration or enforced script; Ruff absent from the existing virtual environment. Violations and format drift were not measured |
| ESLint / Prettier enforcement | Prettier is installed, but no configured lint/format gate. No measured style baseline |
| Frozen sidecar build, real-model acceptance, native installation | Not run for this documentation change |

No coverage percentage, model-quality score or performance measurement was collected. A passing synthetic browser test does not establish model quality or native webview behavior.

## Current tests and gaps

`tests/frontend/` contains Node tests of pure utilities (pagination, source-page parsing, updates, evaluation presentation and session analysis). There is no Vitest/React Testing Library component suite. However, the existing production-build browser smoke script already exercises real React interactions: PDF retry and notes, all eight mode dialogs, duration choices, submit/review, subject selection, bilingual guides, AI setup and Settings. The specification should build on this coverage rather than describe all UI interaction testing as absent.

Prioritise tests for exam switching with a delayed response from the previous exam, preparation polling/cancellation, duplicate submissions, failed/deferred evaluation, and keyboard dialog focus restoration/Escape. The existing browser script is large and combines many workflows; split reusable HTTP fixtures before extending it substantially. Manual screen-reader use, platform webviews and native menu behavior remain separate checks. No automated accessibility audit was run.

Backend tests already cover stale-answer/Skip behavior, accepted/current evidence, backups, schema compatibility, malformed model output and exam isolation. Extend a named uncovered failure path instead of duplicating that suite. Passing tests do not prove arbitrary process-termination recovery.

## Architecture and coupling

| Module | Lines at baseline | Responsibilities and extraction considerations |
| --- | --- | --- |
| `backend/core/services/database.py` | 1,402 | SQLite connections, schema/migrations and broad record access. Migration/backup behavior is high risk; preserve old-workspace regressions before extraction |
| `backend/core/services/grounded_training.py` | 619 | Candidate contracts, generation, evidence/duplicate validation, evaluation and skipped-answer support. Deterministic question validation is a plausible first extraction after mapping helper dependencies |
| `backend/core/services/exam_state.py` | 537 | Selection, sessions, clocks, state transitions, persistence and reports. Preserve transaction boundaries and expected-question semantics if extracting pure score/report calculation |

Line count indicates scope, not measured cyclomatic complexity. Callers cross the legacy `services` import boundary established by `backend/__init__.py`; reorganising packages can change module identity and shared state. Keep compatibility exports until callers and tests migrate. The UI, typed HTTP contracts, orchestration and domain layers are distinct, but large domain modules and the broad browser smoke script remain maintenance debt.

## CI and reproducibility

- `ci.yml` runs npm checks, API/domain tests, production build, sidecar smoke and locked Rust checking in one macOS job. Failures stop the job; later checks then have no result. There are no enforced Ruff, ESLint, format, Clippy or Python type gates.
- `pdf-reader.yml` runs the synthetic production-CSP browser suite separately on Linux. `desktop.yml` reuses it and builds three native targets. Overlapping workflows can duplicate expensive installs/builds.
- `learning-quality.yml` downloads actual Ollama models for backend-related pull requests as well as explicit calls. The specification's intended fast deterministic path therefore needs an explicit trigger decision; a separate workflow alone does not make model downloads opt-in.
- npm and Cargo have lockfiles. Python requirements include version ranges and no full resolved lock; upgrades can change transitive builds. Browser binaries are installed separately. Native build prerequisites and signed release assets require their own evidence.
- Existing workflows use read-only top-level permissions, with release-specific permissions where needed. Workflow action versions, runner images and actual hosted outcomes were not revalidated by running GitHub Actions here.

## Reliability findings and specification adjustments

Observed documentation defects were an obsolete README hero screenshot, absent practice-mode comparison, and claims that signed updates were unconfigured despite the current updater key and 0.1.6+ update implementation. These were corrected without claiming current publisher-signing credentials or successful installation.

No new exploitable security defect was established by this documentation audit. Process-local jobs/locks, one backend per workspace, inference variability and incomplete native acceptance are known limits, not newly reproduced failures.

Refine the supplied specification as follows:

1. **Define a migration gate precisely.** Pin Ruff/ESLint/Prettier versions, measure current violations, then fail on new violations with a reviewed ratchet or explicit per-file legacy exceptions. Checking only selected changed files can hide new violations in a legacy file. Separate formatting commits from behavior changes.
2. **Make aggregate checks predictable.** Add real `make lint`, `format-check`, `typecheck` and `check` targets only when their tools and baseline exist. Keep model downloads and native packaging outside routine deterministic `make check`; document prerequisites and an explicit heavier command.
3. **Extend existing UI coverage.** Add isolated component tests for race conditions and accessibility while retaining the existing Chromium/WebKit CSP checks. Use HTTP-boundary fixtures; do not introduce a second implementation of practice state in tests.
4. **Characterize one extraction.** First map callers and helper dependencies, add focused tests, move a bounded pure function/interface, preserve imports, then run the domain/API suites. Do not combine this with database-schema or state-machine redesign.
5. **Separate model acceptance triggers.** Keep explicit dispatch and release acceptance; agree which model-sensitive PRs require expensive inference. A deterministic backend change should have a path that does not pull weights automatically.
6. **Report proof by scope.** A schema/support-quote gate is not proof of semantic truth; a research citation is not validation of AI grades; a native build is not clean-machine installation. Keep those limits in public docs and reports.

## Handover

| Area | Baseline | Changes in this branch | Verification | Remaining gaps |
| --- | --- | --- | --- | --- |
| Python | Existing domain/API regressions; no configured static-analysis gate | Recorded baseline and change contracts | 65 domain + 124 backend tests passed | Ruff measurement/ratchet, focused type checking |
| Frontend | Strict TS, 17 utility tests, broad browser smoke | Current UI captures and mode documentation; clearer synthetic exam name and clean-picker capture in smoke script | npm tests/build and Chromium/WebKit passed | Component race tests and accessibility coverage |
| Architecture | Layered app with large domain modules and import compatibility | Architecture, standards, ADR and three source-linked case studies | Source/test inspection; existing regression suites passed | One behavior-preserving extraction |
| AI reliability | Evidence gates and regression/real-model workflows exist | Documented exact checks and limitations | Deterministic suites passed; no real-model run | Additional targeted failure paths; model acceptance |
| CI/CD | Packaging/browser checks, model downloads on backend PRs; no style gates | Documented triggers and reproducibility risks; legitimate existing CI badge | Workflow inspection only | Enforced static checks, trigger/caching work, hosted verification |
| Documentation | Stale screenshots/release text; PR #4 still draft | README, practice guide, refreshed screenshots, contracts and measured review | Screenshots inspected; local links checked | Keep screenshots and baseline dated with future changes |

The broad engineering specification is **not complete**. Tooling enforcement, component tests, reliability additions, extraction and CI redesign should be independently reviewable follow-up changes; none is claimed as implemented here.
