# Engineering standards and quality gates

This is the review contract for Colloquily. It describes observable behavior and tests, rather than claiming an unmeasured quality score.

## Non-negotiable invariants

| Invariant | What must remain true | Representative tests or checks |
| --- | --- | --- |
| Local-first privacy | Inference and stored exam materials remain local; no silent cloud fallback/telemetry | `tests/core/test_local_model_routing.py`, `backend/tests/test_model_policy.py`, security review |
| Exam isolation | An exam cannot read another exam's materials, index, questions, answers or progress | `tests/core/test_local_workspace.py`, `backend/tests/test_api.py` |
| Evidence lineage | Questions cite accepted current evidence; stale/rejected evidence cannot silently justify answers | `tests/core/test_subject_quality_pipeline.py`, `backend/tests/test_generation_quality.py` |
| Failure visibility | Empty/invalid model output is a failure or review state, never a fabricated successful result | Generation-quality regressions; local-model acceptance workflow |
| Practice integrity | Skip is ungraded, durable and idempotent; late answers cannot grade another question | `tests/core/test_exam_state.py`, `tests/core/test_oral_evaluation_regressions.py` |
| Persistence safety | Existing workspaces migrate without destructive loss; backup/restore preserves integrity | `backend/tests/test_storage.py`, `backend/tests/test_api.py` |
| Desktop access control | Packaged API is loopback-only with token and Origin/Host checks; sidecar exits with app | `scripts/smoke_sidecar.py`, `docs/security-review.md` |
| UX consistency | English/German parity; critical actions have pending/error states and preserve exam context | `npm test`, TypeScript production build, manual interaction checks |

The named checks are relevant **coverage areas**, not a promise that each one exhaustively proves the invariant. For high-risk changes, add explicit focused tests.

## Definition of done

A change is reviewable when it has: (1) a clear problem and scope; (2) compatible API and data contracts; (3) regression coverage for successful, invalid, stale and interrupted paths as appropriate; (4) no new privacy/security regression; (5) updated translations and documentation where user-visible; and (6) honest verification evidence. Do not merge a failed quality gate by weakening assertions or deleting useful tests.

## Verification ladder

| Level | Command / activity | When |
| --- | --- | --- |
| Frontend translations, utilities, version | `npm test` | Frontend, i18n and general PRs |
| Python API/storage/model adapter regressions | `npm run test:api` | Backend and contract changes |
| Python domain regression suite | `python scripts/test_core.py` | Domain/evidence/practice changes |
| Frontend compile and bundle | `npm run build` | Frontend or API type changes |
| Rust compile check | `cargo check --locked --manifest-path src-tauri/Cargo.toml` | Desktop changes |
| Frozen sidecar verification | `npm run build:sidecar` and `python scripts/smoke_sidecar.py` | Packaging / lifecycle changes |
| Real-model synthetic acceptance | `.github/workflows/learning-quality.yml`, `scripts/smoke_learning_quality.py` | Grounding/evaluation/model changes |
| Native installer acceptance | Clean-machine install, open, prepare, practise, exit, relaunch | Release sign-off |

The CI workflows automate a subset of this ladder, while native packaging runs on target OS/architecture. Real-model acceptance uses synthetic content and externally downloaded model weights; model-based variability and hardware constraints remain relevant. Do not present a green TypeScript or Rust check as proof of functional desktop installation.

## Coding and review expectations

- Keep side effects explicit and isolate storage, model and network boundaries from pure transformations where practical.
- Use Pydantic/TypeScript contracts at the transport boundary; validate model-generated structures and source IDs at domain boundaries.
- Prefer idempotent and atomic state transitions. Identify which state is durable and which is only in process memory.
- Avoid silent catch-and-ignore paths for user-critical data; surface actionable errors with stable codes where applicable.
- Use bounded retries and cancelable jobs for long operations; never block routine navigation on a model request.
- Test with synthetic exam fixtures and temporary data directories. Keep real study materials, generated indexes and secrets out of git.
- Resist unrelated rewrites: large historical modules are candidates for incremental extraction only after characterization tests exist.
- Keep documentation truthful: distinguish implemented guarantees, test observations, known risks, and future intentions.

## Architectural debt worth addressing incrementally

These are maintainability opportunities, not release-blocking bugs established by this document:

1. Several core service files contain multiple responsibilities (notably `database.py`, `grounded_training.py`, and `exam_state.py`). Extract behind tested behavior rather than creating a parallel rewrite.
2. The preserved core's import-path compatibility in `backend/__init__.py` deserves an explicit migration plan before reorganizing packages.
3. Expand automated frontend interaction/accessibility coverage beyond current utility-level regressions.
4. Reduce the measured legacy Ruff/ESLint/format baseline incrementally; new violations and modified unformatted files fail the [developer quality gate](DEVELOPMENT.md).
5. Add clean-machine native release evidence and signing for production distribution. See `desktop.md`.

Making a decision record for one of these improvements is often more valuable than introducing a new library.
