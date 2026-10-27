# Colloquily 0.1.5 — Guided setup and explained practice

This preview makes it easier to move from a new exam and lecture PDFs to a
practice session, and explains what each practice mode is designed to train.

## What changed

- A visible setup path connects exam topic, PDF upload, local AI setup and
  practice. Exams without prepared questions reopen on Materials, and the
  preparation panel is visible by default.
- Eight practice-mode cards show their learning focus. Each mode has a guide
  with a learning goal, concrete practice instructions, timing and feedback
  details. The guide is available before and during a run in English and German.
- Expandable research notes cite studies on retrieval practice, self-explanation,
  formative feedback, distributed practice and interleaving. The explanations
  distinguish evidence for learning principles from rehearsal of an exam format.
- The local model library offers Qwen 2.5 1.5B, Qwen 3 4B/8B and Gemma 3 4B,
  plus suitable installed models. Download multiple candidates and select an
  installed feedback model per exam; other task and embedding settings are kept.
- Study answers, detailed questions, feedback and source passages render
  Markdown, tables and LaTeX math locally. PDF notes have a rendered preview
  and Markdown export; processed study passages can also be exported with
  their source locations and review labels.
- Multi-subject selection now reflects the session requirements: two or three
  exams for Multiple subjects, exactly three for Full colloquium.
- Browser regression checks cover formula rendering and exports, first-run
  creation, mode guides, research-link handling, language switching and model
  selection under the desktop security policy.

No database migration is needed. Existing documents, notes and practice history
remain in the workspace. Automatic equation OCR is not included: check and
correct uncertain extracted formulas against the original PDF. Model choices
are comparison candidates, not benchmarked quality rankings. Speech is not
assessed; practice evaluation uses submitted text.

## Downloads

- Apple Silicon macOS 14+: `Colloquily_0.1.5_aarch64.dmg`
- Intel macOS 14+: `Colloquily_0.1.5_x64.dmg`
- Windows x64: `Colloquily_0.1.5_x64-setup.exe`
- Matching license archives, `LICENSE`, `NOTICE` and `SHA256SUMS.txt`

This is an unsigned preview. Install the update manually; signed automatic
updates are unavailable. Publication requires all three native builds,
real-model learning acceptance and the production Chromium/WebKit regression
on the tagged revision. Local AI model weights remain separate downloads.
