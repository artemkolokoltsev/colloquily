from __future__ import annotations

import config


def _trim(text: str, max_chars: int = 1200) -> str:
    text = (text or "").strip()
    return text if len(text) <= max_chars else f"{text[:max_chars].rstrip()} ..."


def build_qa_prompt(question: str, contexts: list[dict], strict_rag: bool = True) -> str:
    if contexts:
        context_blocks = []
        for idx, item in enumerate(contexts, start=1):
            citation_id = item.get("citation_id", f"Q{idx}")
            label = f"{citation_id}: {item['doc_name']}, Seite {item['page_number']}, {item['source_type']}, chunk={item['chunk_type']}"
            context_blocks.append(f"[{label}]\n{_trim(item['text'])}")
        context_text = "\n\n".join(context_blocks)
    else:
        context_text = "Keine Quellen gefunden."
    strict_line = (
        "Antworte ausschliesslich auf Basis der Quellen. Wenn die Information nicht in den Quellen steht, sage das klar."
        if strict_rag
        else "Bevorzuge die Quellen. Wenn etwas fehlt, kennzeichne die Unsicherheit deutlich."
    )
    return (
        "Du bist ein lokaler Lernassistent fuer Medizintechnik. Antworte auf Deutsch, praezise und lernorientiert.\n"
        f"{strict_line}\n"
        "Setze direkte Quellenhinweise unmittelbar nach den relevanten Aussagen in der Form [Q1], [Q2] oder [Q1][Q2].\n"
        "Nutze nur die angegebenen Quellen-IDs. Wenn eine Aussage nicht belegt ist, sage das klar.\n\n"
        f"Frage:\n{question}\n\n"
        f"Kontext:\n{context_text}\n\n"
        "Antwort:"
    )


def build_page_summary_prompt(doc_name: str, page_number: int, text: str) -> str:
    return (
        "Erstelle eine sehr knappe Lernzusammenfassung auf Deutsch.\n"
        "Format: 4 bis 6 Stichpunkte, zentrale Begriffe, pruefungsrelevante Kernaussagen.\n"
        f"Dokument: {doc_name}\n"
        f"Seite: {page_number}\n\n"
        f"Inhalt:\n{_trim(text, config.SUMMARY_PAGE_TEXT_CHARS)}\n\n"
        "Zusammenfassung:"
    )


def build_multi_page_summary_prompt(doc_name: str, page_items: list[dict]) -> str:
    excerpts = []
    for item in page_items:
        excerpts.append(f"[Seite {item['page_number']}]\n{_trim(item['text'], config.SUMMARY_MULTI_PAGE_TEXT_CHARS)}")
    joined = "\n\n".join(excerpts)
    return (
        "Fasse die folgenden Vorlesungsseiten fuer die Klausurvorbereitung auf Deutsch zusammen.\n"
        "Bleibe knapp, behalte Seitenverweise bei und nenne nur die wichtigsten Begriffe und Zusammenhaenge.\n"
        f"Dokument: {doc_name}\n\n"
        f"Seiteninhalt:\n{joined}\n\n"
        "Zusammenfassung:"
    )


def build_summary_synthesis_prompt(doc_name: str, partial_summaries: list[dict]) -> str:
    blocks = []
    for item in partial_summaries:
        blocks.append(f"[Seiten {item['label']}]\n{_trim(item['summary'], 700)}")
    joined = "\n\n".join(blocks)
    return (
        "Verdichte die folgenden Teilzusammenfassungen fuer die Klausurvorbereitung.\n"
        "Antworte auf Deutsch in kurzen Stichpunkten und behalte die Seitenbereiche bei.\n"
        f"Dokument: {doc_name}\n\n"
        f"Teilzusammenfassungen:\n{joined}\n\n"
        "Endgueltige Zusammenfassung:"
    )


def build_quiz_prompt(topic_or_instruction: str, contexts: list[dict], n_questions: int) -> str:
    context_blocks = []
    for idx, item in enumerate(contexts, start=1):
        label = f"Quelle {idx}: {item['doc_name']}, Seite {item['page_number']}, {item['source_type']}"
        context_blocks.append(f"[{label}]\n{_trim(item['text'], 900)}")
    joined = "\n\n".join(context_blocks) if context_blocks else "Keine Quellen verfuegbar."
    return (
        "Erstelle deutsche klausurartige Uebungsfragen fuer Medizintechnik.\n"
        f"Erzeuge genau {n_questions} Fragen. Mische kurze Freitextfragen und Multiple-Choice, wenn passend.\n"
        "Gib zu jeder Frage eine kurze Musterloesung oder Loesungsschluessel an und nenne passende Quellen.\n"
        f"Thema oder Anweisung: {topic_or_instruction}\n\n"
        f"Kontext:\n{joined}\n\n"
        "Quiz:"
    )


def build_quiz_json_prompt(topic_or_instruction: str, contexts: list[dict], n_questions: int) -> str:
    context_blocks = []
    for idx, item in enumerate(contexts, start=1):
        citation_id = item.get("citation_id", f"Q{idx}")
        label = f"{citation_id}: {item['doc_name']}, Seite {item['page_number']}, {item['source_type']}"
        context_blocks.append(f"[{label}]\n{_trim(item['text'], 700)}")
    joined = "\n\n".join(context_blocks) if context_blocks else "Keine Quellen verfuegbar."
    return (
        "Erstelle Multiple-Choice-Lernfragen fuer Medizintechnik und antworte ausschliesslich als JSON.\n"
        f"Erzeuge genau {n_questions} Fragen.\n"
        "JSON-Format: "
        '[{"question":"...","options":["A","B","C","D"],"correct_answer":"...","explanation":"...","sources":["Q1","Q2"]}]\n'
        "Die correct_answer muss exakt einem Eintrag aus options entsprechen.\n"
        "Keine Markdown-Umrandung, keine Zusatzerklaerung ausserhalb des JSON.\n"
        f"Thema: {topic_or_instruction}\n\n"
        f"Kontext:\n{joined}\n\n"
        "JSON:"
    )
