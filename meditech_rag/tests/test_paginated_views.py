import os
import tempfile
import unittest
from unittest.mock import patch

import config
from app import app
from services.database import create_subject, init_db


class PaginatedViewsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = patch.object(config, 'DB_PATH', os.path.join(self.temp.name, 'test.db'))
        self.db.start()
        init_db()
        self.subject = create_subject('Pagination fixture')
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['active_subject_id'] = self.subject['id']
        self.questions = [dict(id=i, question_text=f'Question {i:02d} full text', topic_name='Alpha' if i < 12 else 'Beta',
                               question_type='explain', difficulty='easy', expected_duration_seconds=60,
                               expected_core_points=[{'text': 'Example answer'}], review_status='accepted', enabled=True)
                          for i in range(1, 24)]

    def tearDown(self):
        self.db.stop()
        self.temp.cleanup()

    def test_library_page_boundaries_and_filter_preservation(self):
        with patch('app.list_questions', return_value=self.questions):
            page = self.client.get('/questions?page=2').get_data(as_text=True)
            self.assertIn('Question 11 full text', page)
            self.assertNotIn('Question 10 full text', page)
            self.assertNotIn('Question 21 full text', page)
            filtered = self.client.get('/questions?topic=Beta&q=Question&page=99').get_data(as_text=True)
            self.assertIn('Page 2 of 2', filtered)
            self.assertIn('Question 23 full text', filtered)
            self.assertIn('topic=Beta', filtered)
            self.assertIn('q=Question', filtered)
            empty = self.client.get('/questions?q=missing').get_data(as_text=True)
            self.assertIn('No questions match these filters', empty)
            self.assertIn('0–0 of 0', empty)

    def test_management_table_is_paginated(self):
        with patch('app.list_questions', return_value=self.questions):
            response = self.client.get(f'/admin/subjects/{self.subject["id"]}/questions?page=3')
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('Question 23 full text', page)
        self.assertNotIn('Question 20 full text', page)

    def test_progress_defaults_to_topics_and_paginates_review_queue(self):
        progress = dict(attempts_count=23, average_score=3, average_response_seconds=45, due_questions=self.questions,
                        topics=[], frequently_missing=[], misconceptions=[], failure_modes=[], failure_topics=[], failure_trend=[])
        with patch('app.subject_progress', return_value=progress):
            overview = self.client.get(f'/progress/{self.subject["id"]}').get_data(as_text=True)
            self.assertNotIn('Question 01 full text', overview)
            queue = self.client.get(f'/progress/{self.subject["id"]}?view=questions&page=2').get_data(as_text=True)
            self.assertIn('Question 11 full text', queue)
            self.assertNotIn('Question 21 full text', queue)
            self.assertIn('view=questions', queue)
