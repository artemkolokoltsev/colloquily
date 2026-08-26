#!/usr/bin/env python3
"""
Extract numbered questions from a PDF into CSV.

Expected input style:
1. Question text...
2. Question text...

The script:
- extracts text with PyMuPDF
- removes repeated headers/footers
- detects numbered questions
- joins multiline questions
- writes CSV and JSON output

Usage:
python scripts/extract_questions_from_pdf.py \
  --pdf "Uebungen/Fragenkatalog.pdf" \
  --out "data/eval/datasets/question_catalog.csv"
"""

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    raise SystemExit(
        "PyMuPDF is missing. Install it with:\n\n"
        "pip install pymupdf\n"
    )


QUESTION_START_RE = re.compile(
    r"^\s*(?P<number>\d{1,4})[\.\)]\s+(?P<text>.+)$"
)

PAGE_NUMBER_RE = re.compile(
    r"^\s*(seite\s*)?\d+\s*(/|von)?\s*\d*\s*$",
    re.IGNORECASE,
)


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def extract_pages(pdf_path: Path) -> list[dict]:
    doc = fitz.open(pdf_path)
    pages = []

    for page_index, page in enumerate(doc):
        text = page.get_text("text")
        lines = [normalize_line(line) for line in text.splitlines()]
        lines = [line for line in lines if line]

        pages.append(
            {
                "page_number": page_index + 1,
                "lines": lines,
            }
        )

    return pages


def find_repeated_header_footer_lines(pages: list[dict], min_ratio: float = 0.30) -> set[str]:
    """
    Finds lines that appear on many pages.
    These are likely headers/footers.

    We do not remove lines that look like question starts.
    """
    page_count = len(pages)
    line_counter = Counter()

    for page in pages:
        unique_lines = set(page["lines"])
        for line in unique_lines:
            line_counter[line] += 1

    repeated = set()
    threshold = max(2, int(page_count * min_ratio))

    for line, count in line_counter.items():
        if count >= threshold:
            if not QUESTION_START_RE.match(line):
                repeated.add(line)

    return repeated


def should_skip_line(line: str, repeated_lines: set[str]) -> bool:
    if not line:
        return True

    if line in repeated_lines:
        return True

    if PAGE_NUMBER_RE.match(line):
        return True

    # Common document noise patterns
    noise_patterns = [
        r"^fragenkatalog$",
        r"^übungen$",
        r"^uebungen$",
        r"^vorlesung",
        r"^rwth",
        r"^meditec",
        r"^seite\s+\d+",
    ]

    lower = line.lower().strip()
    for pattern in noise_patterns:
        if re.match(pattern, lower):
            return True

    return False


def extract_questions(pages: list[dict], repeated_lines: set[str]) -> list[dict]:
    questions = []
    current = None

    for page in pages:
        page_number = page["page_number"]

        for raw_line in page["lines"]:
            line = normalize_line(raw_line)

            if should_skip_line(line, repeated_lines):
                continue

            match = QUESTION_START_RE.match(line)

            if match:
                # Save previous question
                if current:
                    current["question"] = clean_question_text(current["question"])
                    questions.append(current)

                q_number = int(match.group("number"))
                q_text = match.group("text").strip()

                current = {
                    "id": f"q{q_number:03d}",
                    "number": q_number,
                    "question": q_text,
                    "source_page": page_number,
                    "topic": "",
                    "question_type": "",
                    "difficulty": "",
                    "expected_doc": "",
                    "expected_page": "",
                    "include_retrieval_eval": "true",
                    "include_answer_eval": "",
                    "include_case_study": "",
                }
            else:
                # Continuation line of current question
                if current:
                    current["question"] += " " + line

    if current:
        current["question"] = clean_question_text(current["question"])
        questions.append(current)

    return questions


def clean_question_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()

    # Remove spaces before punctuation
    text = re.sub(r"\s+([,.;:?!])", r"\1", text)

    return text


def write_csv(questions: list[dict], out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "id",
        "number",
        "question",
        "source_page",
        "topic",
        "question_type",
        "difficulty",
        "expected_doc",
        "expected_page",
        "include_retrieval_eval",
        "include_answer_eval",
        "include_case_study",
    ]

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for q in questions:
            writer.writerow(q)


def write_json(questions: list[dict], out_path: Path):
    json_path = out_path.with_suffix(".json")
    json_path.write_text(
        json.dumps(questions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_debug_text(pages: list[dict], out_path: Path):
    debug_path = out_path.with_suffix(".debug.txt")

    parts = []
    for page in pages:
        parts.append(f"\n\n--- PAGE {page['page_number']} ---\n")
        parts.extend(page["lines"])

    debug_path.write_text("\n".join(parts), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pdf",
        required=True,
        help="Path to Fragenkatalog.pdf",
    )
    parser.add_argument(
        "--out",
        default="data/eval/datasets/question_catalog.csv",
        help="Output CSV path",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Also write extracted raw text to .debug.txt",
    )
    parser.add_argument(
        "--min-header-ratio",
        type=float,
        default=0.30,
        help="Lines appearing on this ratio of pages are treated as repeated headers/footers.",
    )

    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    out_path = Path(args.out)

    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    pages = extract_pages(pdf_path)
    repeated_lines = find_repeated_header_footer_lines(
        pages,
        min_ratio=args.min_header_ratio,
    )

    questions = extract_questions(pages, repeated_lines)

    if not questions:
        raise SystemExit(
            "No questions found. Check the debug text with:\n\n"
            f"python scripts/extract_questions_from_pdf.py --pdf '{pdf_path}' --out '{out_path}' --debug\n"
        )

    write_csv(questions, out_path)
    write_json(questions, out_path)

    if args.debug:
        write_debug_text(pages, out_path)

    print(f"Extracted questions: {len(questions)}")
    print(f"CSV saved to: {out_path}")
    print(f"JSON saved to: {out_path.with_suffix('.json')}")

    print("\nFirst 5 questions:")
    for q in questions[:5]:
        print(f"{q['number']}. {q['question'][:120]}")


if __name__ == "__main__":
    main()