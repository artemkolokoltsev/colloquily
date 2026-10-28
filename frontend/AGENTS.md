# Frontend-specific instructions

Applies to `frontend/`. Read the root `AGENTS.md` first.

- React/TypeScript is the presentation and interaction layer; the backend owns exam state, evaluation, source validation, persistence, and model selection.
- Keep typed API access centralized in `frontend/src/api/client.ts` and synchronize changed contracts with `frontend/src/types/index.ts` and Pydantic models.
- Always handle loading, empty, cancellation, failure, and stale-response states; never show an operation as completed before the backend confirms it.
- Switching exams must clear or re-scope pending UI data. Do not leak another exam's materials, jobs, practice, or progress.
- Preserve keyboard operation, visible focus, accessible labels, reduced-motion needs, contrast, and responsive layouts.
- New user-facing text belongs in English and German translations. Check key/interpolation parity rather than embedding untranslated strings.
- Render material/model content as text, not trusted HTML. Do not introduce `dangerouslySetInnerHTML`, unsafe navigation, or direct shell access.

Run `npm test` and `npm run build` for frontend changes. Extend `tests/frontend/` for testable UI utilities or add an appropriate regression route when changing user interaction.
