from __future__ import annotations

import json
import os
from typing import Any

import config


SETTINGS_SCHEMA = [
    {
        "section": "Chunking",
        "anchor": "chunking",
        "description": "Parameter fuer die Textsegmentierung vor Embedding und Retrieval.",
        "fields": [
            {"key": "CHUNKING_STRATEGY", "label": "Chunking Strategy", "type": "select", "options": ["page", "word", "paragraph", "semantic", "structure"], "description": "Waehlt, wie Seiten in Retrieval-Einheiten zerlegt werden.", "influences": "Beeinflusst Granularitaet, Zitatgenauigkeit, Duplicate-Ratio und wie viel Kontext einzelne Treffer enthalten."},
            {"key": "CHUNK_SIZE", "label": "Chunk Size", "type": "int", "description": "Wortfenster fuer den Word-Chunker.", "influences": "Groessere Werte geben mehr Kontext pro Treffer, kleinere Werte verbessern oft Praezision und feinere Zitate."},
            {"key": "CHUNK_OVERLAP", "label": "Chunk Overlap", "type": "int", "description": "Ueberlappung zwischen benachbarten Word-Chunks.", "influences": "Reduziert harte Kontextabbrueche, kann aber Duplikate im Retrieval erhoehen."},
            {"key": "PARAGRAPH_GROUP_SIZE", "label": "Paragraph Group Size", "type": "int", "description": "Wie viele Abschnitte der Paragraph-Chunker zusammenfasst.", "influences": "Steuert, ob eher feine Lernkarten oder grobere Erklaerblaecke entstehen."},
            {"key": "PARAGRAPH_OVERLAP", "label": "Paragraph Overlap", "type": "int", "description": "Ueberlappung zwischen Paragraph-Gruppen.", "influences": "Hilft bei weichen Uebergaengen zwischen Abschnitten, auf Kosten zusaetzlicher Aehnlichkeiten."},
            {"key": "MAX_CHUNK_CHARS", "label": "Max Chunk Chars", "type": "int", "description": "Maximale Zeichenzahl fuer semantische und strukturierte Chunks.", "influences": "Begrenzt, wie gross strukturierte Chunks werden duerfen und damit wie dicht Information pro Treffer gepackt ist."},
            {"key": "TOP_K", "label": "Top K", "type": "int", "description": "Wie viele Retrieval-Treffer an die Antworterstellung uebergeben werden.", "influences": "Mehr Treffer vergroessern den Kontext fuer die Antwort, koennen aber auch Rauschen und Promptlaenge erhoehen."},
            {"key": "STRICT_RAG", "label": "Strict RAG", "type": "bool", "description": "Begrenzt Antworten staerker auf den gefundenen Kontext.", "influences": "Hilft gegen Halluzinationen, kann aber Antworten knapper und konservativer machen."},
        ],
    },
    {
        "section": "PDF Parsing",
        "anchor": "pdf-parsing",
        "description": "Steuert die lokale PDF-Extraktion, Strukturaufbereitung und Parserwahl.",
        "fields": [
            {"key": "PDF_PARSER_BACKEND", "label": "Parser Backend", "type": "select", "options": ["pymupdf", "marker"], "description": "Primärer lokaler Parser fuer PDF-Inhalte.", "influences": "Bestimmt Lesereihenfolge, Blockstruktur, Heading-Erkennung und damit die Qualitaet aller spaeteren Chunks und Topics."},
            {"key": "ENABLE_MARKER_FALLBACK", "label": "Enable Marker Fallback", "type": "bool", "description": "Versucht bei schwacher Parsing-Qualitaet auf Marker zu wechseln, falls lokal installiert.", "influences": "Kann schwierige PDFs robuster machen, fuehrt aber je nach Dokument zu anderen Block- und Textstrukturen."},
            {"key": "ENABLE_BLOCK_EXTRACTION", "label": "Enable Block Extraction", "type": "bool", "description": "Extrahiert Textbloecke mit Lesereihenfolge und Koordinaten fuer bessere Struktur.", "influences": "Verbessert Heading-Erkennung, strukturierte Chunkgrenzen und Seiten-/Block-Provenienz."},
            {"key": "ENABLE_STRUCTURE_AWARE_CHUNKING", "label": "Structure-aware Chunking", "type": "bool", "description": "Laesst Parserprofile die Chunking-Methode in Richtung Struktur/Paragraph steuern.", "influences": "Verbessert oft die Nutzbarkeit von Folien und Listen, weil nicht nur starre Textfenster entstehen."},
            {"key": "ENABLE_PARSER_PROFILES", "label": "Enable Parser Profiles", "type": "bool", "description": "Aktiviert Profil-Erkennung fuer Sparse Slides, Textnotizen und Mischlayouts.", "influences": "Beeinflusst Cleanup, Heading-Heuristik und welche Chunking-Art fuer verschiedene PDF-Typen bevorzugt wird."},
            {"key": "PARSER_PROFILE", "label": "Parser Profile", "type": "select", "options": ["auto", "slides_sparse", "slides_dense", "text_notes", "mixed_layout", "scanned_or_low_quality"], "description": "Legt das Profil fuer Cleanup, Heading-Heuristiken und Chunking fest.", "influences": "Steuert, wie aggressiv Folienstruktur erkannt und geglaettet wird."},
            {"key": "MARKER_OUTPUT_FORMAT", "label": "Marker Output Format", "type": "select", "options": ["json", "markdown"], "description": "Bevorzugtes lokales Ausgabeformat fuer Marker, falls verwendet.", "influences": "Aendert, welche Strukturinformationen Marker spaeter fuer Tabellen, Gleichungen und Bilder liefern koennte."},
            {"key": "MARKER_CPU_ONLY", "label": "Marker CPU Only", "type": "bool", "description": "Hält Marker auf CPU-Pfade, damit die App lokal und GPU-frei bleibt.", "influences": "Beeinflusst Laufzeit und Hardwarebedarf, nicht die semantische Logik."},
            {"key": "MARKER_MAX_PAGES", "label": "Marker Max Pages", "type": "int", "description": "Optionales Seitenlimit fuer Marker; 0 bedeutet kein Limit.", "influences": "Begrenzt Parsing-Aufwand und kann bei sehr grossen Dokumenten als Performance-Schranke dienen."},
        ],
    },
    {
        "section": "Retrieval",
        "anchor": "retrieval",
        "description": "Beeinflusst Metadaten-Reranking, Zusammenfassungen und Topic-Ableitung.",
        "fields": [
            {"key": "ENABLE_METADATA_ENRICHMENT", "label": "Metadata Enrichment", "type": "bool", "description": "Berechnet Keywords, Rollen, Topic-Signale und Qualitaetsflags.", "influences": "Verbessert Topic- und Strukturwissen fuer Retrieval, Debugging und spaetere Auswertung."},
            {"key": "ENABLE_METADATA_RERANK", "label": "Metadata Rerank", "type": "bool", "description": "Gewichtet Retrieval-Treffer anhand von Topics, Rollen und Qualitaetsflags nach.", "influences": "Verlagert, welche Quellen in Antworten und Quizzen oben landen."},
            {"key": "SUMMARY_PAGE_TEXT_CHARS", "label": "Summary Page Chars", "type": "int", "description": "Maximale Seitenlaenge pro Zusammenfassungs-Prompt.", "influences": "Bestimmt, wie viel Seitentext in die Zusammenfassung gelangt und ob Details abgeschnitten werden."},
            {"key": "SUMMARY_MULTI_PAGE_TEXT_CHARS", "label": "Summary Multi-page Chars", "type": "int", "description": "Begrenzt Textmenge pro Multi-Page-Zusammenfassung.", "influences": "Balanciert Detailtiefe gegen Promptlaenge fuer Bereichszusammenfassungen."},
            {"key": "SUMMARY_BATCH_PAGES", "label": "Summary Batch Pages", "type": "int", "description": "Wie viele Seiten gemeinsam zusammengefasst werden, bevor ein Synthese-Prompt folgt.", "influences": "Steuert, ob Zusammenfassungen eher lokal pro Seitenblock oder globaler verdichtet werden."},
            {"key": "TOPIC_REGION_MIN_SCORE", "label": "Topic Region Min Score", "type": "float", "description": "Mindestscore fuer das Gruppieren benachbarter Seiten in Topic-Regionen.", "influences": "Beeinflusst, wie schnell benachbarte Seiten als zusammenhaengendes Themengebiet gelten."},
            {"key": "TOPIC_REGION_MAX_GAP", "label": "Topic Region Max Gap", "type": "int", "description": "Erlaubte Seitendistanz innerhalb einer Topic-Region.", "influences": "Bestimmt, wie locker oder streng Topic-Regionen ueber Seitenlaeufe verbunden werden."},
        ],
    },
    {
        "section": "Modelle & Inferenz",
        "anchor": "models",
        "description": "Modelle, Backends und lokale Inferenzendpunkte fuer Embeddings und Antwortgenerierung.",
        "fields": [
            {"key": "EMBED_BACKEND", "label": "Embedding Backend", "type": "select", "options": ["st", "lmstudio"], "description": "Waehlt den Embedding-Pfad: lokal via Sentence-Transformers oder LM Studio.", "influences": "Aendert die semantische Aehnlichkeitssuche und damit, welche Seiten/Chunks ueberhaupt gefunden werden."},
            {"key": "ST_EMBED_MODEL", "label": "Sentence Transformer Model", "type": "text", "description": "Lokales Modell fuer CPU-Embeddings mit Sentence-Transformers.", "influences": "Beeinflusst semantische Treffgenauigkeit, Spracheignung und CPU-Laufzeit."},
            {"key": "ST_ALLOW_DOWNLOAD", "label": "Allow Model Download", "type": "bool", "description": "Erlaubt den einmaligen Download eines fehlenden Sentence-Transformer-Modells.", "influences": "Beeinflusst nur Beschaffung/Startverhalten, nicht die Logik selbst."},
            {"key": "LMSTUDIO_EMBED_MODEL", "label": "LM Studio Embed Model", "type": "text", "description": "Modellname fuer Embeddings ueber die lokale LM-Studio-API.", "influences": "Aendert Retrieval-Semantik, sofern LM Studio als Embedder aktiv ist."},
            {"key": "LLM_BACKEND", "label": "LLM Backend", "type": "select", "options": ["ollama", "lmstudio"], "description": "Waehlt das lokale Antwortmodell ueber Ollama oder LM Studio.", "influences": "Steuert Antwortstil, Robustheit, Promptverhalten und lokale Laufzeit."},
            {"key": "OLLAMA_URL", "label": "Ollama URL", "type": "text", "description": "Basis-URL der lokalen Ollama-Instanz.", "influences": "Bestimmt, wohin lokale Generierungsanfragen geschickt werden."},
            {"key": "OLLAMA_LLM_MODEL", "label": "Ollama Model", "type": "text", "description": "Standardmodell fuer Fragen, Zusammenfassungen und Quizze.", "influences": "Beeinflusst Antwortqualitaet, Halluzinationsneigung, Stil und Geschwindigkeit."},
            {"key": "OLLAMA_TIMEOUT_SECONDS", "label": "Ollama Timeout", "type": "int", "description": "Timeout fuer lokale Ollama-Requests.", "influences": "Entscheidet, wie schnell lange Anfragen abgebrochen werden."},
            {"key": "OLLAMA_NUM_PREDICT", "label": "Ollama Num Predict", "type": "int", "description": "Antwortbudget fuer Ollama in Tokens.", "influences": "Steuert Laenge und Vollstaendigkeit der Antwort."},
            {"key": "LMSTUDIO_BASE_URL", "label": "LM Studio Base URL", "type": "text", "description": "Basis-URL der lokalen LM-Studio-API; Chat- und Embedding-Endpunkte werden daraus abgeleitet.", "influences": "Bestimmt, welche lokale LM-Studio-Instanz fuer Embeddings/Chat verwendet wird."},
            {"key": "LMSTUDIO_LLM_MODEL", "label": "LM Studio Model", "type": "text", "description": "Standardmodell fuer LM-Studio-Chat-Requests.", "influences": "Beeinflusst Stil, Genauigkeit, Halluzinationsrisiko und Inferenzzeit."},
            {"key": "LMSTUDIO_TIMEOUT_SECONDS", "label": "LM Studio Timeout", "type": "int", "description": "Timeout fuer lokale LM-Studio-Requests.", "influences": "Legt fest, wann lange LM-Studio-Antworten als zu spaet gelten."},
            {"key": "LMSTUDIO_MAX_TOKENS", "label": "LM Studio Max Tokens", "type": "int", "description": "Antwortbudget fuer LM Studio.", "influences": "Beeinflusst Ausfuehrlichkeit und ob Antworten abgeschnitten werden."},
            {"key": "LLM_TEMPERATURE", "label": "LLM Temperature", "type": "float", "description": "Sampling-Temperatur fuer lokale Antwortgenerierung.", "influences": "Niedrige Werte machen Antworten stabiler, hohe Werte kreativer aber potenziell ungenauer."},
        ],
    },
]


def _schema_map() -> dict[str, dict]:
    return {field["key"]: field for section in SETTINGS_SCHEMA for field in section["fields"]}


def default_runtime_settings() -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for key in _schema_map():
        defaults[key] = getattr(config, key)
    return defaults


def _coerce_value(value: Any, field_type: str) -> Any:
    if field_type == "bool":
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "on", "yes"}
    if field_type == "int":
        return int(value)
    if field_type == "float":
        return float(value)
    return str(value)


def _apply(settings: dict[str, Any]) -> dict[str, Any]:
    merged = default_runtime_settings()
    merged.update({key: value for key, value in settings.items() if key in _schema_map()})
    for key, value in merged.items():
        setattr(config, key, value)
    config.LMSTUDIO_EMBEDDINGS_URL = f"{config.LMSTUDIO_BASE_URL.rstrip('/')}/v1/embeddings"
    config.LMSTUDIO_CHAT_URL = f"{config.LMSTUDIO_BASE_URL.rstrip('/')}/v1/chat/completions"
    return merged


def initialize_runtime_settings() -> dict[str, Any]:
    settings = load_runtime_settings()
    return _apply(settings)


def load_runtime_settings() -> dict[str, Any]:
    if not os.path.exists(config.RUNTIME_SETTINGS_PATH):
        return default_runtime_settings()
    with open(config.RUNTIME_SETTINGS_PATH, "r", encoding="utf-8") as handle:
        stored = json.load(handle)
    return _apply(stored)


def save_runtime_settings_from_form(form: dict[str, Any]) -> dict[str, Any]:
    schema = _schema_map()
    current = default_runtime_settings()
    if os.path.exists(config.RUNTIME_SETTINGS_PATH):
        with open(config.RUNTIME_SETTINGS_PATH, "r", encoding="utf-8") as handle:
            current.update({key: value for key, value in json.load(handle).items() if key in schema})
    updated = dict(current)
    for key, field in schema.items():
        field_type = field["type"]
        if field_type == "bool":
            updated[key] = key in form and _coerce_value(form.get(key), "bool")
            continue
        raw_value = form.get(key)
        if raw_value is None:
            continue
        raw_value = str(raw_value).strip()
        if field_type == "password" and not raw_value:
            continue
        if raw_value == "" and field_type not in {"text", "password"}:
            continue
        updated[key] = _coerce_value(raw_value, "text" if field_type in {"text", "password", "select"} else field_type)
    applied = _apply(updated)
    with open(config.RUNTIME_SETTINGS_PATH, "w", encoding="utf-8") as handle:
        json.dump(applied, handle, ensure_ascii=False, indent=2)
    return applied


def build_settings_sections(values: dict[str, Any] | None = None) -> list[dict]:
    values = values or load_runtime_settings()
    sections: list[dict] = []
    for section in SETTINGS_SCHEMA:
        fields = []
        for field in section["fields"]:
            item = dict(field)
            item["description"] = f"Configure {field['label'].lower()} for local processing."
            item["influences"] = "Changes local parsing, retrieval, or model behaviour; rebuild the relevant exam index when required."
            if field["type"] == "password":
                item["value"] = ""
                item["has_saved_value"] = bool(values.get(field["key"]))
            else:
                item["value"] = values.get(field["key"], getattr(config, field["key"], ""))
            fields.append(item)
        sections.append(
            {
                "section": "Models & Inference" if section["section"] == "Modelle & Inferenz" else section["section"],
                "anchor": section.get("anchor", section["section"].lower().replace(" ", "-").replace("&", "and")),
                "description": {
                    "chunking": "Configure how source text becomes retrieval evidence.",
                    "pdf-parsing": "Configure local PDF extraction and structure detection.",
                    "retrieval": "Configure local retrieval, reranking, and summaries.",
                    "models": "Configure local embedding and answer-generation services.",
                }.get(section.get("anchor"), "Configure local application behaviour."),
                "fields": fields,
            }
        )
    return sections
