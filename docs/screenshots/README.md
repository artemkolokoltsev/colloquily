# UI reference screenshots

Capture screenshots from a running release candidate with a disposable `COLLOQUILY_DATA_DIR` and synthetic material. Never add personal exams, documents, paths, or model history.

The current English workflow captures were refreshed on **2026-10-28** from the 0.1.9 production browser build, using the existing synthetic HTTP fixtures in [the browser smoke script](../../scripts/smoke_pdf_reader.mjs). They render the actual React UI under the desktop content-security policy. No personal workspace or inference model is used. The grades and feedback shown are fixtures, not measured AI output or a native installer acceptance run.

| View | Capture |
| --- | --- |
| Eight practice modes | [Mode picker](practice-modes-en.png) |
| Learning goals, method and research notes | [Mode guide](practice-guide-en.png) |
| Focused question, timer and answer | [Practice session](practice-session-en.png) |
| Original cited PDF page within practice | [Source insight](source-insight-en.png) |
| Scores, skips, submitted answer and feedback | [Session results](session-results-en.png) |
| Language and backup controls | [Settings](settings-en.png) |

To reproduce from the repository root, install npm dependencies and Playwright browsers, then run:

```bash
npm run test:pdf
```

The smoke script runs Chromium and WebKit and writes captures to ignored `output/playwright/`. Inspect before copying to this directory. Use these Chromium outputs for the current references:

| Output | Published filename |
| --- | --- |
| `practice-modes-ready-chromium.png` | `practice-modes-en.png` |
| `practice-learning-chromium.png` | `practice-guide-en.png` |
| `practice-ambient-chromium.png` | `practice-session-en.png` |
| `insight-source-chromium.png` | `source-insight-en.png` |
| `session-analysis-chromium.png` | `session-results-en.png` |
| `settings-refined-chromium.png` | `settings-en.png` |

The older [exam-creation](exam-creation-en.png) and [German settings](settings-de.png) captures are retained as historical references; they are not current 0.1.9 UI captures. The browser test checks German interactions too, but does not currently publish a matching refreshed German screenshot.
