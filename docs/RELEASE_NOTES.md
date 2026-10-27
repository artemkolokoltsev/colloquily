# Colloquily 0.1.6 — Focused practice and reliable updates

Choose a visual practice card, explore what it trains, then start from a focused
setup dialog. The session shows the question and your answer with minimal
controls; feedback has its own view before you continue.

- Eight illustrated mode cards retain learning-theory explanations and research
  references. Session options live inside the mode dialog.
- Previous runs are removed from Practice. An unfinished current session can
  resume; completed progress remains available from Home.
- The duplicate setup navigation is removed. Materials handles PDF preparation,
  the sidebar handles navigation, and the app name/version stays at bottom right.
- The tagline is now “Exam workspace” (localized in German).
- Software updates check on launch, every six hours and after reconnection, with
  visible status, progress, a manual install action and an automatic-update toggle.
- Downloads are verified before workspace backup and installation. Automatic
  restart waits for an idle Home screen, offers a 30-second countdown and Later,
  and is blocked during practice, processing or unsaved Home edits. Interaction
  resets the countdown. Install/restart failures release the workspace lock.
- Permanent website download links track new releases without website edits.
  The signed update feed uses immutable versioned payloads for all three platforms.

## Installation and release status

**Users of 0.1.5 and earlier must install this version manually once.** Those
builds contain a placeholder updater key. After this bootstrap, subsequent
higher-version releases can install through the corrected updater.

This is an OS-unsigned preview, with signed updater artifacts. Apple notarization
and Windows Authenticode remain separate from updater verification. macOS 14+
(Apple Silicon or Intel) and Windows x64 installers are built by CI. Internet is
needed for update checks/downloads; exams, PDFs and answers remain local.

Automatic updates can include previews. Disable the option under Software
updates for manual checking. Backups precede installation, but keep your own
independent copies of important material. Local AI still requires Ollama.

Website integration and permanent URLs: [DOWNLOADS.md](DOWNLOADS.md).
