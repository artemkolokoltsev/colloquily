from __future__ import annotations

import os
import sys


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.rag_engine import RAGEngine


def main() -> None:
    engine = RAGEngine()
    print("Stats:", engine.get_stats())
    questions = [
        "Welche Themen sind in den hochgeladenen Vorlesungen besonders pruefungsrelevant?",
        "Fasse wichtige Definitionen aus den Vorlesungen zusammen.",
        "Welche Geraetebeispiele oder Anwendungen werden erwaehnt?",
    ]
    for idx, question in enumerate(questions, start=1):
        result = engine.answer_question(question)
        print(f"\nFrage {idx}: {question}")
        print("Antwortlaenge:", len(result["answer"]))
        print("Quellen:")
        for source in result["contexts"]:
            print(
                f"  - {source['doc_name']} | Seite {source['page_number']} | "
                f"chunk_type={source['chunk_type']} | source_type={source['source_type']} | "
                f"score={source.get('score', 0):.3f}"
            )


if __name__ == "__main__":
    main()
