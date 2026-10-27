# Colloquily 0.1.9 — Source insights and clearer session review

- Filter detected course logistics and outline-only passages out of study evidence, including previously accepted material. Keep originals and historical answers available. Require supported comparison questions and use a separate validation pass with the configured answering model.
- Fix retrieval so it can return several relevant passages from one document.
- Insight previews the actual cited PDF page, preserving formulas and diagrams. Includes enlargement, retry, and secondary extracted text.
- Session results show question-score charts, evaluated/skipped/ungraded counts, and feedback-based suggestions. Submitted answers are visible, repeated feedback is removed, and Previous/Next controls simplify review.
- End session now finalizes submitted work, clears timers and cannot be reopened by delayed polling. Pending or unreliable evaluations are not scored as zero.
- Choose 5, 10, 15, 30, 45, 60 or 90 minutes using duration cards. Time applies to the whole session, or separately to each subject block, including preparation.
- Move update controls into About Colloquily, accessible from the sidebar, Settings and native About menu. Include app, storage, privacy and feedback information. Background updates continue without a permanent workspace banner.
- Refine Settings with English/Deutsch cards that save immediately. Fix progress display and dark-mode contrast; completed jobs use compact confirmations without stale percentages.

## Preview and updates

Study-content filters reduce unsupported questions but do not guarantee AI correctness. Check uncertain feedback against the original sources. Existing materials and answers are retained.

This preview includes signed updater payloads. Native publisher trust is recorded separately in the per-platform trust reports and requires configured signing credentials.

Permanent website download URLs remain unchanged. Version 0.1.6 and later can receive this release through the signed updater; earlier versions need a manual download.

Local verification: 124 backend/API tests, 65 core tests and 17 frontend tests passed, along with translation checks, production build, Rust check, and Chromium/WebKit browser regressions. Native installers and real-model learning acceptance are checked by the release workflow before publication.
