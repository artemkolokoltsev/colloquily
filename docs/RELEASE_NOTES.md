# Colloquily 0.1.12 — Material formatting and responsive source review

## Fixes

- **Bounded material details.** Source review fetches and displays ten passages at a time, with Previous/Next controls. Collapsed review sections do not mount their passages. Opening one document no longer loads the whole course's review list or duplicates it in hidden Advanced tools.
- **Original pages on demand.** Use **View original page** on a passage to load its PDF preview. Scrolling through extracted text no longer starts many PDF downloads, workers and canvases.
- **Readable extracted text.** Source line breaks are preserved alongside Markdown lists, tables and LaTeX math. Table-of-contents rows no longer run together into a single paragraph. The original PDF remains the visual reference for positioned equations and layouts.
- **Contents pages are reference material.** Spaced dot-leader contents entries are excluded from explanatory study evidence, including evidence accepted by older versions. Review shows a Table of contents label. Raw text, saved review decisions and past answers are retained.
- Unsaved passage edits block page navigation until saved or cancelled. Closing and reopening Details or Advanced tools preserves corrections and the current passage page while Materials remains open. Failed passage requests can be retried; stale requests are cancelled on navigation.

Existing lecture-script revisions, exercise solutions and submission settings remain available. No database schema change is required. Existing extracted passages benefit from the display fix without reprocessing.

## Verification

Regressions cover a thousand-passage library, bounded DOM and network requests, scrolling, deferred PDF loading, line breaks, math/tables, page boundaries, exam isolation, superseded evidence and legacy accepted contents pages. Native packaging, real-model acceptance and browser checks gate publication through the existing signed-preview channel.

This remains an updater-signed preview. OS publisher trust is recorded separately in the platform trust files. PDF export for exercise submissions still requires local TeX.

## Deutsch

- Die Quellenprüfung lädt und zeigt zehn Abschnitte pro Seite. Eingeklappte Bereiche erzeugen keine versteckten Abschnittslisten.
- Original-PDFs werden erst über **Originalseite anzeigen** geladen; Scrollen startet keine zusätzlichen PDF-Vorschauen.
- Zeilenumbrüche bleiben erhalten, Markdown-Tabellen und LaTeX-Formeln werden weiterhin dargestellt.
- Inhaltsverzeichnisse mit Punktlinien bleiben als Referenz sichtbar und werden von der Fragenerstellung ausgeschlossen. Das gilt auch für früher akzeptierte Belege; gespeicherte Entscheidungen und Rohtexte bleiben erhalten.
- Ungespeicherte Änderungen müssen vor dem Seitenwechsel gespeichert oder verworfen werden. Vorhandene Kursdaten bleiben erhalten; eine erneute Extraktion ist für die Anzeige nicht nötig.
