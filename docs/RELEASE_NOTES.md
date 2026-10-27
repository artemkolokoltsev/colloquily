# Colloquily 0.1.8 — Chat and automatic practice evaluation

- Chat replaces Ask with a local conversation per exam, follow-up context, cited sources and clear mathematics.
- Practice evaluation starts automatically when all questions are answered or the timer completes the run. Multi-subject runs evaluate after all subject blocks finish. Failed evaluation offers a retry.
- Fix Mac preview packaging when Apple signing credentials are absent; empty certificate variables no longer trigger a failed keychain import.
- All eight training modes can start. Unfinished runs offer an explicit Resume option instead of hiding the mode picker. Multi-exam selection is visible in the setup dialog.
- The bottom of the left sidebar shows the app name, version, current year and rights notice.
- Includes the guided local AI setup and native-signing support prepared for 0.1.7: start installed Ollama, explicitly download recommended models, and test generation and embeddings.

## Preview and updates

This is a preview with signed updater payloads. OS publisher trust depends on configured Apple/Windows signing credentials and is recorded in the release trust reports. Updater signatures alone do not establish OS publisher trust.

Existing permanent website download URLs stay the same. Apps on 0.1.6 or later can use the signed updater after publication. Earlier versions need a manual download.

Local verification: 117 backend/API tests, 65 core tests, 11 frontend tests, translation checks, production build, and Chromium/WebKit practice and chat regressions passed before the version bump. Native release builds and acceptance gates run on GitHub before publication.
