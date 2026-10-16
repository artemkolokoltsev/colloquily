# Colloquily user guide

Colloquily prepares source-grounded practice for university oral exams. Your
materials, study history and answers stay on your computer. Local AI can make
mistakes: check generated questions and feedback against the cited passages.

## Install and set up

1. Download the installer matching your computer from [Releases](https://github.com/artemkolokoltsev/colloquily/releases), plus its license bundle. See [installation](INSTALLATION.md) for preview-build warnings.
2. Open Colloquily and select English or German. You can change language in Settings without restarting.
3. Install and start [Ollama](https://ollama.com/download). In 0.1.1, Colloquily checks local memory and disk space, reuses suitable installed models, and prepares missing models for the selected exam automatically. Progress offers cancellation and retry. Existing explicit exam model settings are preserved; advanced changes remain under **AI setup**. The older 0.1.0 RC4 preview requires explicit model downloads there. Downloads can be large; keep sufficient free storage.
4. Check the model status before starting AI-powered practice. You can organize exams and materials without a running model.

No Python, Node.js, Docker or terminal is required for the desktop application.
Ollama is a separate installation. Its model terms apply separately; model
weights are not included with Colloquily.

## Prepare an exam

1. Create an exam, name it, choose its language, and optionally set its date.
   Use the exam picker to search and switch exams. Materials and practice history
   belong to the selected exam; switching does not delete another exam's work.
2. Import your own lecture PDFs or Markdown notes under **Materials**. Original documents are kept in that exam's local workspace.
3. Choose **Prepare my practice**. Colloquily extracts study text, creates evidence and prepares questions. Keep the app open while processing.
4. If extraction is uncertain or preparation fails, inspect the material and source-review tools. Poor-quality or unreviewed evidence is excluded from grounded retrieval. Scanned PDFs without extractable text may require a searchable/OCR version prepared separately.
5. Check generated questions, expected points and sources. Review, disable or edit questionable items before practising. Question-pool imports and reported exam questions are available as additional inputs.

In 0.1.1, preparation covers every eligible document/topic batch. A weak model may
produce fewer valid questions than requested: the app retains those results and
shows incomplete coverage rather than inserting filler. Choose **Generate
questions for uncovered topics** to continue. Check each material's **Ready**,
**Needs review** or **Unusable** passages, page counts and extraction issues.
Reprocessing preserves manual review decisions and existing study history.

## Practise and review

Start a single question, topic practice or a timed simulation. Answer in your
own words. Feedback identifies supported, missing and incorrect points and
includes source passages. Open the original source to verify the assessment;
PDF references can jump to a cited page. Scores are learning aids, not an
official university grade.

In 0.1.1, **Skip** advances without calling AI, grading your answer or revealing a
model answer. The attempt is saved as skipped, not correct. Skipping the final
question completes the session; repeated clicks do not skip an extra question.

The Dashboard and study plan show due practice and progress. A full colloquium
uses three selected exams; individual mock sessions remain exam-scoped. Finish
or leave a run through the app controls so progress and workspace activity are
saved consistently.

## Back up and restore

In **Settings**, export a workspace backup before deleting materials or making
major changes. It includes course documents, SQLite study history and settings,
but not Ollama's downloaded models. Store backups somewhere separate from the
computer if you need protection against disk failure.

To restore, select a backup, inspect its preview and confirm replacement. Stop
active processing or practice first. The app validates paths, checksums and
database schema, creates a safety backup and retains replaced workspace files.
Do not restore an archive from an untrusted source.

## Updates and troubleshooting

This unsigned preview must be updated manually. Signed automatic updates are
not enabled for the release candidate; never install an unknown updater file.
Installing a new app version does not intentionally overwrite your workspace.

- **AI unavailable:** start Ollama, check AI setup, and confirm the required models are downloaded.
- **Processing interrupted:** reopen the app, inspect material status and retry the failed operation. Original sources remain local.
- **No eligible questions:** inspect the source review and question statuses; only enabled, accepted material can be used.
- **PDF text missing:** obtain a searchable PDF or convert your material to Markdown. Image-only pages are not silently treated as valid academic text.
- **Restore/update blocked:** finish active practice and wait for processing to complete.

Workspace locations: macOS `~/Library/Application Support/Colloquily/`; Windows
`%APPDATA%\Colloquily\`. Settings displays the actual directory. Do not delete
this directory to troubleshoot without making a backup.

For bug reports, use [GitHub Issues](https://github.com/artemkolokoltsev/colloquily/issues).
Include app version, operating system and reproducible steps. Do not upload
private lecture material, databases, model history or secrets.
