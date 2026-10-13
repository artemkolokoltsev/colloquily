import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

export const en = {
  translation: {
    app: { tagline: "Your local oral-exam workspace", currentExam: "Current exam", createExam: "Create an exam", localPromise: "Local files. Local inference. No cloud account." },
    nav: { dashboard: "Dashboard", materials: "Materials", questions: "Questions", practice: "Practice", progress: "Progress", ask: "Ask your materials", reported: "Reported questions", plan: "Study plan", ai: "AI setup", settings: "Settings", advanced: "Advanced tools" },
    startup: { starting: "Starting your local study workspace…", retry: "Retry connection" },
    setup: { notice: "One-time setup: your local AI needs to be ready before we can prepare questions.", action: "Set up AI" },
    exam: { eyebrow: "Prepare with evidence", title: "What are you preparing for?", intro: "Name your exam, choose a date, then add your lecture PDFs. We’ll prepare your first practice questions.", name: "New exam name", placeholder: "e.g. Quantum physics", date: "Exam date", optional: "optional", create: "Create exam & add PDFs →", defaultDescription: "PDF and Markdown sources, isolated evidence and practice.", minutes: "{{count}}-minute mock exam", open: "Open materials" },
    settings: { title: "Settings", intro: "Language, backups, updates, and advanced local AI settings.", language: "Language", english: "English", german: "Deutsch", dataDirectory: "Data directory: {{path}}", models: "Models for this exam (Ollama)", embedding: "Embedding model", save: "Save settings", saved: "Settings saved. Rebuild the exam index after changing its embedding model.", backup: "Backup and restore", createBackup: "Create workspace backup", backupReady: "Backup created: {{path}}", currentVersion: "Current version: {{version}}", updates: "Application updates", checkUpdates: "Check for updates", noUpdate: "You’re up to date.", updateAvailable: "Version {{version}} is available.", installUpdate: "Install and restart", updateFailed: "Could not check for updates. You can keep using Colloquily offline." },
    common: { completed: "Completed", failed: "Failed", answerFeedback: "Answer feedback", correct: "Correct", missing: "Missing", incorrect: "Incorrect", source: "Source {{count}}", openSource: "Open original source", closeSource: "Close source", operationFailed: "Operation failed", languageChanged: "Language changed" },
    errors: { EXAM_NAME_REQUIRED: "Enter an exam name.", SOURCE_TYPE_UNSUPPORTED: "Only PDF and Markdown files are accepted.", SOURCE_NOT_FOUND: "The source no longer exists.", RESTORE_CONFIRMATION_REQUIRED: "Confirm that restore may replace the current workspace.", BACKUP_INVALID: "This is not a valid Colloquily backup.", BACKUP_SCHEMA_NEWER: "This backup was created by a newer Colloquily version.", BACKUP_CHECKSUM_MISMATCH: "The backup is damaged or incomplete.", unknown: "Something went wrong. Try again or check the local log." },
  },
} as const;

const de = { translation: {
  app: { tagline: "Dein lokaler Arbeitsbereich für mündliche Prüfungen", currentExam: "Aktuelle Prüfung", createExam: "Prüfung erstellen", localPromise: "Lokale Dateien. Lokale KI. Kein Cloud-Konto." },
  nav: { dashboard: "Übersicht", materials: "Materialien", questions: "Fragen", practice: "Üben", progress: "Fortschritt", ask: "Materialien befragen", reported: "Prüfungsprotokollfragen", plan: "Lernplan", ai: "KI einrichten", settings: "Einstellungen", advanced: "Erweiterte Werkzeuge" },
  startup: { starting: "Dein lokaler Lernbereich wird gestartet…", retry: "Verbindung erneut versuchen" },
  setup: { notice: "Einmalige Einrichtung: Die lokale KI muss bereit sein, bevor Fragen erstellt werden können.", action: "KI einrichten" },
  exam: { eyebrow: "Mit Quellen lernen", title: "Auf welche Prüfung bereitest du dich vor?", intro: "Benenne die Prüfung, wähle optional ein Datum und füge deine Vorlesungsunterlagen hinzu.", name: "Name der neuen Prüfung", placeholder: "z. B. Quantenphysik", date: "Prüfungsdatum", optional: "optional", create: "Prüfung erstellen & PDFs hinzufügen →", defaultDescription: "PDF- und Markdown-Quellen, isolierte Belege und Übungen.", minutes: "{{count}} Minuten Prüfungssimulation", open: "Materialien öffnen" },
  settings: { title: "Einstellungen", intro: "Sprache, Sicherungen, Updates und erweiterte lokale KI-Einstellungen.", language: "Sprache", english: "English", german: "Deutsch", dataDirectory: "Datenordner: {{path}}", models: "Modelle für diese Prüfung (Ollama)", embedding: "Embedding-Modell", save: "Einstellungen speichern", saved: "Einstellungen gespeichert. Erstelle den Prüfungsindex nach einem Wechsel des Embedding-Modells neu.", backup: "Sichern und wiederherstellen", createBackup: "Arbeitsbereich sichern", backupReady: "Sicherung erstellt: {{path}}", currentVersion: "Aktuelle Version: {{version}}", updates: "Programmaktualisierungen", checkUpdates: "Nach Updates suchen", noUpdate: "Colloquily ist aktuell.", updateAvailable: "Version {{version}} ist verfügbar.", installUpdate: "Installieren und neu starten", updateFailed: "Die Updatesuche ist fehlgeschlagen. Colloquily kann offline weiterverwendet werden." },
  common: { completed: "Abgeschlossen", failed: "Fehlgeschlagen", answerFeedback: "Antwortfeedback", correct: "Richtig", missing: "Fehlend", incorrect: "Falsch", source: "Quelle {{count}}", openSource: "Originalquelle öffnen", closeSource: "Quelle schließen", operationFailed: "Vorgang fehlgeschlagen", languageChanged: "Sprache geändert" },
  errors: { EXAM_NAME_REQUIRED: "Gib einen Prüfungsnamen ein.", SOURCE_TYPE_UNSUPPORTED: "Es werden nur PDF- und Markdown-Dateien unterstützt.", SOURCE_NOT_FOUND: "Die Quelle ist nicht mehr vorhanden.", RESTORE_CONFIRMATION_REQUIRED: "Bestätige, dass die Wiederherstellung den aktuellen Arbeitsbereich ersetzen darf.", BACKUP_INVALID: "Dies ist keine gültige Colloquily-Sicherung.", BACKUP_SCHEMA_NEWER: "Diese Sicherung wurde mit einer neueren Colloquily-Version erstellt.", BACKUP_CHECKSUM_MISMATCH: "Die Sicherung ist beschädigt oder unvollständig.", unknown: "Etwas ist schiefgelaufen. Versuche es erneut oder prüfe das lokale Protokoll." },
} };

export const resources = { en, de } as const;

void i18n.use(LanguageDetector).use(initReactI18next).init({
  resources,
  fallbackLng: "en",
  supportedLngs: ["en", "de"],
  load: "languageOnly",
  interpolation: { escapeValue: false },
  detection: { order: ["localStorage", "navigator"], caches: ["localStorage"], lookupLocalStorage: "colloquily.language" },
});

export default i18n;
