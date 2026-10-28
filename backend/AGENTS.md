# Backend-specific instructions

Applies to `backend/` including `backend/core/`. Read the repository `AGENTS.md` first.

## Layers and ownership

- `backend/launcher.py`: owns loopback listener and frozen sidecar entry point.
- `backend/main.py`: lifecycle, request access controls, and exclusive-workspace gate.
- `backend/api/routes.py` and `backend/models/api.py`: HTTP transport and Pydantic contracts.
- `backend/services/`: desktop/API orchestration, jobs, model setup and maintenance.
- `backend/core/services/`: exam domain, source review, SQLite, question and evidence logic, FAISS and local model adapters.
- `backend/__init__.py` exposes the preserved core's `config` and `services` imports via a compatibility path. Do not casually rename or duplicate these modules.

## Invariants and tests

- Validate untrusted inputs at the API boundary; enforce authorization/exam ownership and safe file operations in services too.
- All source evidence must be exam-scoped, approved, and current when used to index, generate, answer or evaluate.
- Preserve raw extracts and provenance when normalizing source text. An LLM's recommendation is not approval.
- Use bounded timeouts, explicit statuses and recoverable failure for model and processing operations. Do not hide failures as success.
- Preserve transactionality and idempotency of practice state transitions, especially Skip and late answers. Never let an old answer grade the next question.
- Keep SQLite mutations compatible with existing workspaces; test migrations with synthetic old schemas and isolated temp directories. Do not operate on real `data/` in tests.
- Keep model endpoints restricted to local loopback unless product/security requirements are deliberately revised.

Relevant tests live under `backend/tests/` and `tests/core/`. Run, at minimum:

```bash
npm run test:api
python scripts/test_core.py
```

For evidence, generation, scoring or ingestion edits, add focused regression cases in the existing suites. For local-model quality changes, use `scripts/smoke_learning_quality.py` only with explicitly prepared models and report nondeterminism.
