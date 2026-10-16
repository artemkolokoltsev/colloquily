# Colloquily 0.1.1 — patch draft (not release-approved)

Prepared after the published 0.1.0 RC4 preview. No new release has been published.

## Changes

- Searchable exam picker, quieter desktop chrome, adaptive light/dark appearance,
  English/German student workflows and clearer document/evidence review.
- Automatic resource-aware local Ollama model preparation, installed-model reuse,
  download progress/cancellation/retry and preservation of exam-specific settings.
- Multi-document, topic-aware question preparation with resumable validated
  results, coverage reporting and no passage-quotation fallback.
- Source quotes, citation/claim checks, semantic duplicate checks and comparison
  quality gates. Weak models produce explicit limitations, not filler questions.
- Skip no longer runs AI evaluation or generates answer feedback. Skipped attempts
  persist, advance idempotently and complete the last question correctly.
- Reprocessing preserves unchanged citation IDs and manual review decisions;
  historical questions/progress are retained even when sources become ineligible.

## Release gates

Windows x64, Intel macOS and Apple Silicon native CI builds pass, including
packaged-backend and license/source checks. Final real-model quality/coverage
acceptance and clean-machine GUI installation checks remain outstanding.
See [the verification report](LEARNING_QUALITY_PATCH.md).
The local Intel macOS build is for validation, not a signed production installer.
Signing/notarization and updater credentials remain separate release requirements.

Before tagging a release, review these gates and copy the approved release notes
to `docs/RELEASE_NOTES.md`, which the existing publishing workflow consumes.
Do not overwrite or retag the already published RC4 assets.
