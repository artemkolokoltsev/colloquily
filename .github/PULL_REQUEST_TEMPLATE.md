## Purpose and scope

What user or engineering problem does this solve? What deliberately remains out of scope?

## Design and compatibility

Affected layers, API/data changes, migrations, and any relevant ADR:

## Verification performed

- [ ] `make check` (lint, formatting, strict types, deterministic tests and build)

- [ ] `npm test`
- [ ] `npm run test:api`
- [ ] `python scripts/test_core.py`
- [ ] `npm run build`
- [ ] Platform/sidecar checks (if applicable; specify)
- [ ] Local-model acceptance (if applicable; specify)
- [ ] Manual UX/accessibility checks (if applicable; specify)

Include actual results. Mark skipped checks as **not run** with the reason; never imply success.

## Invariant checklist

- [ ] Exam isolation, current source evidence and question history remain correct
- [ ] No silent cloud fallback, telemetry, or data disclosure introduced
- [ ] Durable state, migration and backup behavior preserved
- [ ] API contracts and English/German translations updated if needed
- [ ] Regression tests and docs/ADR added for changed behavior
- [ ] No personal documents, secrets, models or build artifacts committed

## Risks and follow-up

Known limitations, platform gaps and rollback considerations:
