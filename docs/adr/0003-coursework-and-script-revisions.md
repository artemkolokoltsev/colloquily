# 0003: Versioned scripts and local exercise submissions

Status: implemented in the working tree.

A cumulative lecture script needs one stable document identity even when upload
filenames change. A course can designate an existing PDF on its first update or
create a script. The active raw path and document ID stay stable; slide uploads
remain independent. No filename heuristics guess which unrelated files to delete.

Schema 12 adds `lecture_scripts`, `script_revisions`, `submission_profiles`, and
`exercise_sheets`. The existing migration mechanism snapshots schema 11 before
upgrading. All tables are additive and exam-scoped. PDFs are stored as SQLite
BLOBs in revisions/sheets, trading database size for transactional durability and
inclusion in existing backups. Only the active script is materialized into `raw`;
exercise sheets and student answers are never ingested as lecture evidence.

Script replacement takes the existing exclusive workspace gate. The database
transaction archives the revision, retires all previous evidence (including manual
reviews), clears processing checkpoints and archives page notes. Only then is the
raw PDF replaced atomically. Startup and document listing recover interrupted file
materialization from the committed revision. Retired passages cannot be re-approved;
reprocessing can reuse identical source passages, but reviewed text from the old
version cannot override changed pages. Historical attempts/reviews remain intact.

Exercise solutions use optimistic revision checks. The UI keeps unsaved recovery
drafts on the device, scoped by course and sheet; Save persists them in SQLite.
Submission settings are course-wide and applied at export time. Exports do not
freeze an independent submission record; downloaded PDFs are the user's snapshots.

PDF generation uses a locally installed `pdflatex` with amsmath, amssymb, amsthm,
and geometry. There is no cloud service, new package dependency, or bundled TeX
runtime. The body accepts a bounded list of mathematical/typesetting commands and
environments. Programming, file access and package commands are rejected before
compilation. Shell escape is disabled; each pass has a 30-second timeout and uses
a disposable directory. This is a solution editor, not an arbitrary TeX execution
service. Full `.tex` export supports editing advanced constructs externally.
TeX's file flags alone are not a sandbox: TeX Live 2026 no longer enforces
`openin_any` ([TeX Live updates](https://tug.org/texlive/bugs.html)).

Rollback: stop the app and restore the integrity-checked pre-migration database
and matching workspace backup with the older application. Older builds correctly
reject schema 12. Do not edit migration versions to force a downgrade. Preserve
new submissions/revisions by exporting them before rollback. No existing data is
removed during migration. Native packaging and clean-machine TeX setup remain
separate acceptance steps.
