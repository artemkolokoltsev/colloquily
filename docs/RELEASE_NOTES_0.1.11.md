# Colloquily 0.1.11 — Lecture script revisions and exercise submissions

## New features

- **One evolving lecture script per course.** Upload the professor's updated PDF even when its filename changes. Colloquily keeps one active document, archives earlier PDFs and page notes, and retires outdated evidence immediately. Lecture-by-lecture slides remain separate.
- **Exercise workspace.** Upload an exercise sheet, read it alongside a LaTeX solution editor, and save your work in the course. Device-local recovery drafts preserve edits while navigating.
- **Submission details.** Configure the course name, semester (for example WS26/27), partner names and Matrikelnummern once per course.
- **LaTeX and PDF exports.** Download a complete `.tex` document or compile a submission PDF locally with its course/team header. Preview the actual exported PDF inside Colloquily.
- English and German interface text, saved-draft conflict handling, and version history downloads.

## Getting started

1. Open **Materials → Lecture script**. For a previously uploaded script, select it before the first update. Add separate lecture slides below. Prepare your practice again after updating the script.
2. Open **Exercises**, configure **Submission details**, and upload a sheet. Write the document body in the LaTeX editor; the application adds the preamble and submission header.
3. Save or export. PDF export needs a local `pdflatex` installation with `amsmath`, `amssymb`, `amsthm`, and `geometry`, such as MacTeX or TeX Live. Colloquily does not bundle or download TeX. `.tex` export remains available without it. Advanced macros, custom packages and file commands require external editing of the `.tex` export.

## Data and verification

Schema 12 adds course-scoped script revisions, exercise sheets and submission settings. Existing materials and practice history are retained; migration takes a pre-upgrade database snapshot. Updated page numbers can invalidate annotations, so old page notes stay with the archived script rather than being silently moved to the new pages. Exercise sheets and student solutions are not lecture evidence.

Publication requires deterministic tests, Chromium/WebKit PDF and coursework checks, frozen-backend coursework self-tests, all three native builds, and local-model acceptance. Test results describe the checked scenarios; they are not a guarantee of zero defects or clean-machine installation on every device.

This release continues the signed-preview download/update channel. Updater signatures are separate from OS publisher signing; inspect each platform's trust asset for its verified status. Existing permanent download links and in-app updates remain available.

## Deutsch

- **Fortlaufendes Vorlesungsskript:** Neue PDFs ersetzen die aktive Version; Dateiname und Umfang dürfen sich ändern. Frühere PDFs und Seitennotizen bleiben im Versionsverlauf. Veraltete Belege werden sofort deaktiviert; einzelne Vorlesungsfolien bleiben getrennt.
- **Übungsblätter:** Aufgaben-PDF und LaTeX-Editor nebeneinander, gespeicherte Lösungen und lokale Wiederherstellungsentwürfe.
- **Abgabedaten:** Kursname, Semester, Partnernamen und Matrikelnummern pro Kurs konfigurieren.
- **Export:** Vollständige `.tex`-Datei oder lokal erzeugtes PDF mit Abgabekopf und Vorschau. PDF-Export benötigt eine lokale TeX-Installation; Speichern und `.tex`-Export funktionieren auch ohne sie.

Vorhandene Kursdaten bleiben erhalten. Nach einer Skriptaktualisierung die Übung erneut vorbereiten. Dies ist weiterhin eine Vorschau mit signierten Update-Dateien; Angaben zur Betriebssystemsignatur stehen in den jeweiligen Trust-Dateien.
