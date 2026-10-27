# Colloquily user guide

Colloquily prepares source-grounded practice for university oral exams. Your
materials, study history and answers stay on your computer. Local AI can make
mistakes: check generated questions and feedback against the cited passages.

## Install and set up

1. Download the installer matching your computer from [Releases](https://github.com/artemkolokoltsev/colloquily/releases), plus its license bundle. See [installation](INSTALLATION.md) for preview-build warnings.
2. Open Colloquily and select English or German. You can change language in Settings without restarting.
3. Open **AI setup**. Install Ollama from the official link if needed, then choose **Start local AI**. Review the recommended model and estimated space, choose **Download and prepare local AI**, then **Test local AI**. The sample checks generation and document embeddings without your files. Failed downloads can be retried; the model library remains under Advanced controls. Downloading models requires internet and adequate disk space.
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

Install 0.1.6 manually once if you have 0.1.5 or earlier. Starting with 0.1.6,
Software updates checks for and downloads signed updates automatically. It waits
for two idle minutes on Home, gives a 30-second countdown, and backs up before
installing and restarting. Practice, background work and unsaved Home edits block
automatic restart. Choose Later or disable automatic updates to keep control;
manual checks/install remain available. Offline checks retry after 15 minutes.
See [permanent download links](DOWNLOADS.md).

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


## First-run setup and practice choices

Create an exam, add PDFs in **Materials**, then open **Practice** from the sidebar. Materials shows preparation progress and links to **AI setup** when needed. The exam name is your main subject (for example, Quantum physics). Each exam has its own materials and progress. An exam without prepared questions reopens on Materials after restarting, so you can continue setup. Upload PDFs or Markdown and keep the practice preparation panel open to follow progress, retry preparation, and start a session.

Practice presents all eight modes as illustrated cards. Click a card to open its explanation and settings dialog, then select **Start practising**. Expand session options to adjust time, topic filters, and question count where supported. During practice the sidebar is hidden; answer the question, review feedback, then continue. **End session** returns to the mode picker. Previous runs are not listed here; review progress from Home. Multi-subject modes accept up to three exams. Single-subject modes always use the current exam.

### Comparing local practice models

AI setup includes a model library. You can explicitly download several models, then select an installed model for this exam's answer feedback. Other task choices and the embedding model are preserved. Existing installed text models also appear in the library. Downloads are shared between exams; selections are exam-specific.

The initial comparison set is Qwen 2.5 1.5B (small), Qwen 3 4B (medium), Qwen 3 8B (larger), and Gemma 3 4B (alternative family). Sizes shown are approximate weight downloads, not RAM requirements. These are comparison candidates, not measured quality rankings. Start with the hardware-based recommendation, then compare feedback on the same course questions. Actual inference speed, correctness, and memory use need validation on your machine. Small models may fail preparation quality checks.

Upstream model descriptions and available variants: [Qwen 2.5](https://ollama.com/library/qwen2.5), [Qwen 3](https://ollama.com/library/qwen3), [Gemma 3](https://ollama.com/library/gemma3).

### Readable formulas and Markdown

Study answers, source passages, detailed questions, and feedback support Markdown, tables, and LaTeX mathematics through [react-markdown](https://github.com/remarkjs/react-markdown) and [remark-math / KaTeX](https://github.com/remarkjs/remark-math). Use `$x^2$` for inline math and a `$$` block for display equations. Rendering and fonts work locally without a CDN.

The PDF reader preserves the original visual page. Its notes editor has a rendered preview and **Export notes as Markdown**. **Export study text (.md)** on a material exports its processed passages, source locations, and review status, preserving any LaTeX already present. Process the document first. Review and correct extracted passages against the original PDF before confirming them for practice; corrected passages can contain Markdown and LaTeX.

This does not provide automatic equation OCR or reconstruct missing PDF symbols. A formula stored as positioned glyphs or an image may still require manual transcription. Personal notes stay separate from course evidence. Markdown exports retain review labels and can include passages that still need checking.


### What the practice modes train

Each mode now shows a learning focus, a concrete goal, an instruction for how to practise, and the actual session format. The selected mode's guide includes expandable research notes with citations; it is also available during a run. English and German are supported. Research links open in your browser from the desktop app.

| Mode | Intended practice | Feedback / format |
| --- | --- | --- |
| Single question | Retrieve and explain one concept | Feedback after submission |
| Rapid practice | Give concise, accurate answers | Feedback after each answer; short time budget |
| Weak topic | Identify and repair gaps using earlier attempts | Due questions first, normal pool if no history; evaluate afterward |
| Random practice | Identify the relevant concept in a varied selection | Configurable count and filters; evaluate afterward |
| Oral exam simulation | Structure explanations within a time budget | Configurable count and filters; evaluate afterward |
| Subject simulation | Sustain explanations across one subject | Configured exam duration; evaluate afterward |
| Multiple subjects | Rehearse changing subject context | Two or three consecutive subject blocks; evaluate afterward |
| Full colloquium | Rehearse the complete three-subject format | Exactly three exams, 15 minutes each including preparation; evaluate afterward |

The explanations draw on [retrieval-practice experiments (Roediger & Karpicke, 2006)](https://doi.org/10.1111/j.1467-9280.2006.01693.x), [a self-explanation meta-analysis (Bisra et al., 2018)](https://doi.org/10.1007/s10648-018-9434-x), [feedback research (Hattie & Timperley, 2007)](https://doi.org/10.3102/003465430298487), [a synthesis of distributed practice (Cepeda et al., 2006)](https://doi.org/10.1037/0033-2909.132.3.354), and [a classroom trial of interleaved mathematics practice (Rohrer et al., 2020)](https://doi.org/10.1037/edu0000367).

These are learning principles, not validation of the app's grading or rankings of its modes. The guide distinguishes self-explanation from merely reading aloud, random ordering from deliberate interleaving, and timed format rehearsal from a demonstrated learning benefit. Speech is not assessed; evaluation uses the submitted text. Spacing is advice to revisit material later, not a claim that every mode implements an optimal repetition schedule.

Starting Ollama may leave its background runtime running after Colloquily closes, as with a normal Ollama installation. Use Ollama’s own controls when you want to quit it.


### Chat and automatic practice evaluation

Chat keeps a local conversation for each exam. Enter sends a message; Shift+Enter adds a line. Follow-up messages use the last four saved exchanges for context, with current course evidence providing citations. Personal notes remain opt-in.

Practice always opens the mode picker. An unfinished run offers Resume or End unfinished session; starting another mode ends the unfinished run. Multiple subjects requires two or three exams, and Full colloquium requires exactly three; the exam checkboxes appear directly in the mode dialog. Each selected exam needs eligible accepted questions.

Deferred evaluation starts automatically after the last question or timer expiry completes the run. In multi-subject practice, finish all subject blocks first. Only submitted answers are evaluated; an unsent draft is not submitted when time expires. The summary shows evaluation progress, then grades. If local AI fails, restore it and use Retry evaluation. A run without answers has no grade.

The left sidebar footer shows Colloquily, the installed version, and a copyright notice with the current year. It is hidden with the sidebar during focused practice.
