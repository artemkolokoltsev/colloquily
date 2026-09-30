import unittest

from app import _render_answer_with_citations, _source_page_number, app


class SourceViewerTests(unittest.TestCase):
    def test_page_number_is_recovered_from_subject_source_location(self):
        self.assertEqual(_source_page_number({"source_location": "page 37, lines 4-9"}), 37)
        self.assertEqual(_source_page_number({"source_start": 12, "source_location": "page 3"}), 12)
        self.assertIsNone(_source_page_number({"source_location": "appendix"}))

    def test_inline_citation_uses_subject_metadata_and_explicit_pdf_page(self):
        source = {
            "citation_id": "E42",
            "document_title": "Learning Theory.pdf",
            "relative_path": "lectures/Learning Theory.pdf",
            "source_type": "pdf",
            "source_location": "page 23, lines 5-8",
            "content": "A grounded preview.",
            "source_url": "/subjects/3/raw/lectures/Learning%20Theory.pdf",
        }
        with app.test_request_context("/"):
            rendered = str(_render_answer_with_citations("See [E42].", [source]))

        self.assertIn('data-doc="Learning Theory.pdf"', rendered)
        self.assertIn('data-page="page 23, lines 5-8"', rendered)
        self.assertIn('data-page-number="23"', rendered)
        self.assertIn('data-source-type="pdf"', rendered)
        self.assertIn('data-preview="A grounded preview."', rendered)
        self.assertIn('data-pdf-url="/subjects/3/raw/lectures/Learning%20Theory.pdf"', rendered)
        self.assertIn('onclick="openSourceModal(this)"', rendered)
        self.assertIn("[Learning Theory.pdf · slide 23]", rendered)
        self.assertNotIn("[E42]", rendered)

    def test_unresolved_internal_citation_is_not_exposed(self):
        with app.test_request_context("/"):
            rendered = str(_render_answer_with_citations("Keep [E999] visible.", []))
        self.assertNotIn("[E999]", rendered)


if __name__ == "__main__":
    unittest.main()
