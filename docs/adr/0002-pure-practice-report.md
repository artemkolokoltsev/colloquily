# ADR 0002: Separate pure practice reporting from session transitions

- Status: Accepted
- Date: 2026-10-28

`exam_state.py` owns session persistence, timing and transitions, but also contains
pure grade/report calculations. Move only `german_grade` and `_evaluation_report`
to `practice_report.py`, retaining explicit compatibility imports in `exam_state`.
Existing callers, including generation-quality tests, keep the same names.

Five characterization tests passed before extraction and remain unchanged after:
all grade boundaries/clamping, empty reports, unreliable numeric scores, skips,
zero/None handling, retained evidence and input immutability. Existing integration
tests continue to exercise reports through persisted exam runs.

No schema, transaction, assessment policy or public API changes. Skip still counts
in the session percentage denominator without appearing as an evaluated answer;
pending/review/error scores remain ungraded. This extraction does not address the
larger database or generation modules. Single-file formatting is committed
separately to make the behavior-preserving move reviewable.
