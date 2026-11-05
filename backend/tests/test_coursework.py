"""Coursework migrations, revision safety and export contracts use synthetic data."""

from contextlib import closing
from io import BytesIO
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import backend  # noqa: F401 - initializes compatibility imports
import config
from fastapi import UploadFile
from fastapi.testclient import TestClient
from backend.main import app
from backend.services import coursework, lecture_scripts
from backend.services.solution_latex import validate_solution
from services import database as db, knowledge_repository as knowledge
from services.quality_pipeline import process_subject
from services.subject_workspace import workspace_for
from services.synthetic_pdf import synthetic_pdf
from services.training_repository import accepted_evidence_map


def pdf(text):
    return synthetic_pdf([[(40, 70, text)]])


def upload(name, content):
    return UploadFile(filename=name, file=BytesIO(content))


class CourseworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for key, value in {
            "DB_PATH": str(root / "test.db"),
            "DATA_DIR": str(root),
            "SUBJECTS_DIR": str(root / "exams"),
            "LEGACY_SUBJECTS_DIR": str(root / "legacy"),
            "RUNTIME_SETTINGS_PATH": str(root / "settings.json"),
        }.items():
            context = patch.object(config, key, value)
            context.start()
            self.addCleanup(context.stop)
        db.init_db(seed_admin=False)
        self.subject = db.create_subject("FOLOG")
        self.ident = self.subject["id"]
        self.first = pdf(
            "A directed tree has a designated root, and all edges point toward the root. Tree isomorphism preserves adjacency and root membership."
        )
        self.second = pdf(
            "A rooted tree has a unique root. All directed edges point toward this root. Permutation invariance preserves the value when node order changes."
        )

    def test_revisions_preserve_identity_retire_reviewed_evidence_and_recover(self):
        first = lecture_scripts.replace(
            self.ident, upload("script-until-5.pdf", self.first)
        )
        work = workspace_for(self.subject)
        (work.folder("raw") / "lecture-6.pdf").write_bytes(
            pdf("Separate lecture six slides.")
        )
        process_subject(self.ident, mode="deterministic")
        units = knowledge.list_review_units(
            self.ident, document_id=first["document_id"]
        )
        self.assertTrue(units)
        old = units[0]["id"]
        knowledge.review_unit(
            old,
            "accepted",
            content="The manually corrected old definition must not remain current.",
            subject_id=self.ident,
        )
        from backend.services.page_notes import save_note, notes

        save_note(self.ident, first["document_id"], 1, "An annotation to old page one.")
        self.assertIn(old, accepted_evidence_map(self.ident))
        with patch(
            "backend.services.lecture_scripts.os.replace",
            side_effect=OSError("interrupted"),
        ):
            with self.assertRaises(OSError):
                lecture_scripts.replace(
                    self.ident, upload("script-until-6.pdf", self.second)
                )
        self.assertNotIn(old, accepted_evidence_map(self.ident))
        lecture_scripts.recover()
        current = lecture_scripts.current(self.ident)
        self.assertEqual(current["document_id"], first["document_id"])
        self.assertEqual(current["revision"], 2)
        self.assertEqual(
            (work.folder("raw") / current["relative_path"]).read_bytes(), self.second
        )
        self.assertEqual(len(work.discover_sources()), 2)
        self.assertEqual(lecture_scripts.revision(self.ident, 1)["content"], self.first)
        self.assertIn(
            "old page one", lecture_scripts.revision(self.ident, 1)["notes_json"]
        )
        self.assertEqual(notes(self.ident, first["document_id"]), [])
        with self.assertRaisesRegex(ValueError, "SOURCE_SUPERSEDED"):
            knowledge.review_unit(old, "accepted", subject_id=self.ident)
        process_subject(self.ident, mode="deterministic")
        self.assertNotIn(old, accepted_evidence_map(self.ident))
        self.assertTrue(
            knowledge.list_review_units(self.ident, document_id=first["document_id"])
        )
        same = lecture_scripts.replace(
            self.ident, upload("another-name.pdf", self.second)
        )
        self.assertFalse(same["changed"])
        self.assertEqual(same["revision"], 2)

    def test_adopt_existing_script_without_duplicate_and_reject_cross_exam(self):
        work = workspace_for(self.subject)
        original = work.folder("raw") / "until-lecture-5.pdf"
        original.write_bytes(self.first)
        doc, _ = knowledge.upsert_document(self.ident, work.discover_sources()[0])
        other = db.create_subject("Other course")["id"]
        with self.assertRaises(ValueError):
            lecture_scripts.replace(other, upload("six.pdf", self.second), doc["id"])
        result = lecture_scripts.replace(
            self.ident, upload("six.pdf", self.second), doc["id"]
        )
        self.assertEqual(result["document_id"], doc["id"])
        self.assertEqual(len(work.discover_sources()), 1)
        self.assertEqual(original.read_bytes(), self.second)
        with self.assertRaises(ValueError):
            lecture_scripts.replace(self.ident, upload("broken.pdf", b"broken"))
        self.assertEqual(original.read_bytes(), self.second)

    def test_api_drafts_profiles_isolation_and_export(self):
        with TestClient(app) as client:
            prefix = f"/api/exams/{self.ident}"
            response = client.post(
                prefix + "/exercises",
                files={"file": ("sheet.pdf", self.first, "application/pdf")},
            )
            self.assertEqual(response.status_code, 201, response.text)
            sheet = response.json()
            path = prefix + f"/exercises/{sheet['id']}"
            body = {
                "title": "Exercise 1",
                "latex": r"\section*{Problem 1} Let $G=(V,E)$.\[\mu(X)=\frac{1}{n}X^T\mathbf{1}_n\]",
                "revision": 1,
            }
            self.assertEqual(client.put(path, json=body).status_code, 200)
            self.assertEqual(client.put(path, json=body).status_code, 400)
            details = {
                "course_name": "FOLOG & Graphs",
                "semester": "WS26/27",
                "authors": [
                    {"name": "Ada Müller", "matrikelnummer": "001234"},
                    {"name": "Emmy Noether", "matrikelnummer": "005678"},
                ],
            }
            self.assertEqual(
                client.put(prefix + "/submission-profile", json=details).status_code,
                200,
            )
            tex = client.get(path + "/tex").text
            self.assertIn(r"FOLOG \& Graphs", tex)
            self.assertIn("001234", tex)
            self.assertIn("WS26/27", tex)
            self.assertIn(body["latex"], tex)
            self.assertEqual(client.get(path + "/source").content, self.first)
            self.assertEqual(workspace_for(self.subject).discover_sources(), [])
            other = db.create_subject("Other course")["id"]
            self.assertEqual(
                client.get(f"/api/exams/{other}/exercises/{sheet['id']}").status_code,
                400,
            )
            with patch("backend.services.coursework.latex_engine", return_value=None):
                self.assertFalse(
                    client.get(prefix + "/exercises").json()["pdf_export_available"]
                )
                self.assertEqual(
                    client.post(path + "/pdf").json()["error"]["code"],
                    "LATEX_UNAVAILABLE",
                )
        db.init_db(seed_admin=False)
        self.assertEqual(
            coursework.sheet(self.ident, sheet["id"])["latex"], body["latex"]
        )
        self.assertEqual(coursework.profile(self.ident), details)

    def test_script_api_is_exclusive_during_background_work(self):
        from backend.services.maintenance import gate

        with TestClient(app) as client:
            gate.enter()
            try:
                result = client.put(
                    f"/api/exams/{self.ident}/lecture-script",
                    files={"file": ("script.pdf", self.first)},
                )
                self.assertEqual(result.status_code, 409)
            finally:
                gate.leave()
            result = client.put(
                f"/api/exams/{self.ident}/lecture-script",
                files={"file": ("script.pdf", self.first)},
            )
            self.assertEqual(result.status_code, 200, result.text)

    def test_script_update_waits_for_transient_materials_reads(self):
        from backend.services.maintenance import gate
        from threading import Timer

        with TestClient(app) as client:
            gate.enter()
            release = Timer(0.1, gate.leave)
            release.start()
            try:
                result = client.put(
                    f"/api/exams/{self.ident}/lecture-script",
                    files={"file": ("script.pdf", self.first)},
                )
                self.assertEqual(result.status_code, 200, result.text)
            finally:
                release.join()

    def test_pdf_validates_the_exact_draft_snapshot_it_compiles(self):
        saved = coursework.upload_sheet(self.ident, upload("sheet.pdf", self.first))
        with patch("backend.services.coursework.sheet", return_value=saved) as read:
            source = coursework.submission_tex(self.ident, saved["id"], for_pdf=True)
            read.assert_called_once()
            self.assertIn(saved["latex"], source)
        with patch(
            "backend.services.coursework.sheet",
            return_value={**saved, "latex": r"\input{/etc/passwd}"},
        ):
            with self.assertRaisesRegex(ValueError, "LATEX_UNSUPPORTED_COMMAND"):
                coursework.submission_tex(self.ident, saved["id"], for_pdf=True)

    def test_schema_11_upgrade_preserves_existing_material_and_backup(self):
        work = workspace_for(self.subject)
        (work.folder("raw") / "old.pdf").write_bytes(self.first)
        doc, _ = knowledge.upsert_document(self.ident, work.discover_sources()[0])
        with closing(db._connect()) as connection:
            for table in (
                "lecture_scripts",
                "script_revisions",
                "submission_profiles",
                "exercise_sheets",
            ):
                connection.execute("DROP TABLE " + table)
            connection.execute("DELETE FROM schema_migrations WHERE version=12")
            connection.commit()
        db.init_db(seed_admin=False)
        self.assertEqual(knowledge.list_documents(self.ident)[0]["id"], doc["id"])
        self.assertEqual(coursework.sheets(self.ident), [])
        backup = (
            Path(self.temp.name)
            / "backups/migrations/colloquily-schema-11-before-12.db"
        )
        self.assertTrue(backup.is_file())
        with closing(sqlite3.connect(backup)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT MAX(version) FROM schema_migrations"
                ).fetchone()[0],
                11,
            )
        db.init_db(seed_admin=False)
        self.assertEqual(knowledge.list_documents(self.ident)[0]["id"], doc["id"])

    def test_latex_dialect_blocks_file_execution_and_programming(self):
        for source in [
            r"\input{/etc/passwd}",
            r"\write18{touch test}",
            r"\csname input\endcsname",
            r"\catcode1=2",
            r"^^5cinput{test}",
            r"\begin{filecontents}{x}bad\end{filecontents}",
            r"\newcommand{\bad}{x}",
            r"\end{document}",
        ]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                validate_solution(source)
        validate_solution(
            r"\section*{Problem 1}\begin{proof}Let $P\in\mathbb{R}^{n\times n}$.\[\mu(PX)=\frac{1}{n}X^TP^T\mathbf{1}_n=\mu(X).\]\end{proof}"
        )

    @unittest.skipUnless(coursework.latex_engine(), "Local pdflatex not installed")
    def test_real_pdf_export_contains_header_authors_and_math(self):
        import pypdfium2 as pdfium

        sheet = coursework.upload_sheet(self.ident, upload("exercise.pdf", self.first))
        coursework.save_profile(
            self.ident,
            {
                "course_name": "FOLOG & Graphs",
                "semester": "WS26/27",
                "authors": [
                    {"name": "Ada Müller", "matrikelnummer": "001234"},
                    {"name": "Emmy Noether", "matrikelnummer": "005678"},
                ],
            },
        )
        body = r"\section*{Problem 1}\begin{proof}Let $P$ be a permutation matrix. Then $P^T\mathbf{1}_n=\mathbf{1}_n$, hence\[\mu(PX)=\frac{1}{n}X^TP^T\mathbf{1}_n=\mu(X).\]\end{proof}"
        coursework.save_sheet(
            self.ident,
            sheet["id"],
            {"title": "Exercise 1", "latex": body, "revision": 1},
        )
        validate_solution(body)
        result = coursework.compile_pdf(
            coursework.submission_tex(self.ident, sheet["id"])
        )
        with pdfium.PdfDocument(result) as document:
            with closing(document[0]) as page, closing(page.get_textpage()) as text:
                content = text.get_text_range()
                self.assertIn("WS26/27", content)
                self.assertIn("001234", content)
                self.assertIn("005678", content)
                self.assertIn("Problem 1", content)
        with self.assertRaisesRegex(ValueError, "LATEX_COMPILE_FAILED"):
            coursework.compile_pdf(
                r"\documentclass{article}\begin{document}\undefinedcommand\end{document}"
            )
