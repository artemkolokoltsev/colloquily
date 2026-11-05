"""Bounded material browsing and conservative outline filtering on synthetic data."""

from contextlib import closing
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import backend  # noqa: F401 - initializes compatibility imports
import config
from fastapi.testclient import TestClient
from backend.main import app
from services import database as db, knowledge_repository as knowledge
from services.quality_pipeline import deterministic_cleanup, extract_source_units
from services.study_content import study_content_problem
from services.subject_workspace import workspace_for
from services.synthetic_pdf import synthetic_pdf
from services.training_repository import accepted_evidence_map, create_question

CONTENTS = "Contents\n1 Primer on Graphs . . . . . . 3\n1.1 Basic Set Notation . . . . . . 4\n1.2 Graphs and Degrees . . . . . . 5"
BODY = "A graph consists of vertices and edges.\nA graph is undirected when each edge connects an unordered pair of vertices."


class MaterialReviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for key, value in {
            "DB_PATH": str(self.root / "test.db"),
            "DATA_DIR": str(self.root),
            "SUBJECTS_DIR": str(self.root / "exams"),
            "LEGACY_SUBJECTS_DIR": str(self.root / "legacy"),
            "RUNTIME_SETTINGS_PATH": str(self.root / "settings.json"),
        }.items():
            context = patch.object(config, key, value)
            context.start()
            self.addCleanup(context.stop)
        db.init_db(seed_admin=False)
        self.subject = db.create_subject("Graph theory")
        self.other = db.create_subject("Other course")
        self.ident = self.subject["id"]
        self.document, _ = knowledge.upsert_document(
            self.ident,
            {
                "relative_path": "script.md",
                "title": "Script",
                "source_type": "markdown",
                "source_hash": "fixture",
            },
        )
        workspace_for(self.subject).folder("raw").joinpath("script.md").write_text(BODY)
        units = []
        for page in range(1, 1004):
            unit = deterministic_cleanup(
                {
                    "raw_content": BODY,
                    "source_location": f"page {page}",
                    "source_start": page,
                    "source_end": page,
                }
            )
            units.append(unit)
        knowledge.insert_knowledge_units(self.ident, self.document["id"], units)

    def test_bounded_pages_are_stable_complete_and_exam_scoped(self):
        with TestClient(app) as client:
            prefix = f"/api/exams/{self.ident}/review-page"
            first = client.get(prefix).json()
            self.assertEqual(
                (first["total"], first["limit"], len(first["items"])), (1003, 10, 10)
            )
            self.assertEqual(
                [row["source_start"] for row in first["items"]], list(range(1, 11))
            )
            self.assertNotIn("raw_content", first["items"][0])
            self.assertEqual(first["items"][0]["content"], BODY)
            second = client.get(prefix + "?offset=10&limit=10").json()
            self.assertEqual(
                [row["source_start"] for row in second["items"]], list(range(11, 21))
            )
            self.assertFalse(
                {row["id"] for row in first["items"]}
                & {row["id"] for row in second["items"]}
            )
            last = client.get(prefix + "?offset=1000&limit=10").json()
            self.assertEqual(len(last["items"]), 3)
            self.assertEqual(client.get(prefix + "?offset=2000").json()["items"], [])
            self.assertEqual(
                client.get(
                    f"/api/exams/{self.other['id']}/review-page?document_id={self.document['id']}"
                ).json()["total"],
                0,
            )
            for query in ["offset=-1", "limit=0", "limit=26"]:
                self.assertEqual(client.get(prefix + "?" + query).status_code, 422)

    def test_stats_and_pages_exclude_superseded_extraction(self):
        first = knowledge.review_page(self.ident)["items"][0]
        create_question(
            self.ident,
            {
                "question_text": "What is an undirected graph?",
                "question_type": "explain",
                "evidence_ids": [first["id"]],
            },
        )
        stats = knowledge.list_documents(self.ident)[0]
        self.assertEqual(
            (stats["unit_count"], stats["source_page_count"], stats["question_count"]),
            (1003, 1003, 1),
        )
        with closing(db._connect()) as connection:
            connection.execute(
                "UPDATE knowledge_units SET quality_problems_json='[\"superseded_extraction\"]' WHERE id=?",
                (first["id"],),
            )
            connection.commit()
        stats = knowledge.list_documents(self.ident)[0]
        self.assertEqual(
            (stats["unit_count"], stats["source_page_count"], stats["question_count"]),
            (1002, 1002, 0),
        )
        self.assertEqual(knowledge.review_page(self.ident)["total"], 1002)

    def test_legacy_accepted_contents_are_visible_but_not_study_evidence(self):
        first = knowledge.review_page(self.ident)["items"][0]
        with closing(db._connect()) as connection:
            connection.execute(
                "UPDATE knowledge_units SET content=?,raw_content=?,review_status='accepted',enabled_for_retrieval=1 WHERE id=?",
                (CONTENTS, CONTENTS, first["id"]),
            )
            connection.commit()
        item = knowledge.review_page(self.ident)["items"][0]
        self.assertEqual(
            item["review_status"],
            "accepted",
            "historical review decision remains unchanged",
        )
        self.assertEqual(item["study_problem"], "outline_without_explanation")
        self.assertNotIn(first["id"], accepted_evidence_map(self.ident))
        with closing(db._connect()) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT raw_content FROM knowledge_units WHERE id=?", (first["id"],)
                ).fetchone()[0],
                CONTENTS,
            )

    def test_pdf_extraction_keeps_rows_and_quarantines_contents(self):
        path = self.root / "contents.pdf"
        synthetic_pdf(
            [
                [
                    (40, 70 + number * 25, text)
                    for number, text in enumerate(CONTENTS.splitlines())
                ]
            ],
            path,
        )
        units = extract_source_units({"path": path, "source_type": "pdf"})
        raw = "\n".join(unit["raw_content"] for unit in units)
        self.assertIn("\n1.1 Basic Set Notation", raw)
        result = deterministic_cleanup(
            {"raw_content": raw, "source_location": "page 1"}
        )
        self.assertEqual(result["recommended_status"], "quarantined")
        self.assertEqual(result["raw_content"], raw)

    def test_outline_detection_keeps_real_definitions_and_math(self):
        for text in [
            BODY,
            "The contents of a TCP segment include the header and the payload.",
            "For $x_1,\\ldots,x_n$, let $\\mu(X)=\\frac{1}{n}\\sum_i x_i$.",
            "A sentence with an ellipsis ... followed by a substantive explanation.",
        ]:
            self.assertIsNone(study_content_problem(text))
        self.assertEqual(
            study_content_problem("Contents\n1 Graphs 3\n2 Learning 10"),
            "outline_without_explanation",
        )
