import json
import unittest
from datetime import date
from unittest.mock import patch

import backend
from backend.services.learning import learning_overview


class LearningPlanTests(unittest.TestCase):
    def overview(self, deadline, attempts=(), questions=None, pools=()):
        goal = {'exam_date': deadline, 'repetitions': 3, 'questions_per_session': 2}
        if questions is None:
            questions = [{'id': i, 'topic_name': 'Networks', 'review_status': 'accepted', 'enabled': True} for i in (1, 2)]
        with patch('backend.services.learning.list_question_pools', return_value=list(pools)), patch('backend.services.learning._connect') as connect, patch('backend.services.learning.list_questions', return_value=questions), patch('backend.services.learning._attempt_rows', return_value=list(attempts)):
            connect.return_value.execute.return_value.fetchone.return_value = [json.dumps(goal)]
            return learning_overview(1, 1, today=date(2026, 9, 20))

    def attempt(self, question=1, status='evaluated', score=4, day='2026-09-20'):
        return {'question_id': question, 'evaluation_json': json.dumps({'status': status, 'score': score}), 'created_at': day+'T12:00:00+00:00', 'duration_seconds': 30, 'expected_duration_seconds': 60}

    def test_even_distribution_and_today(self):
        result = self.overview('2026-09-23')
        self.assertEqual([s['questions'] for s in result['plan']['schedule']], [2,2,1,1])
        self.assertEqual(result['plan']['daily_sessions'], 1)
        self.assertEqual(self.overview('2026-09-20')['plan']['daily_questions'], 6)

    def test_no_deadline_past_deadline_and_empty(self):
        self.assertEqual(self.overview(None)['plan']['schedule'], [])
        self.assertTrue(self.overview('2026-09-19')['plan']['overdue'])
        self.assertEqual(self.overview('2026-09-19')['plan']['daily_questions'], 0)
        self.assertEqual(self.overview('2026-09-21', questions=[])['plan']['total'], 0)

    def test_scored_only_and_per_question_cap(self):
        attempts = [self.attempt() for _ in range(5)] + [self.attempt(2, 'skipped', 5), self.attempt(2, 'pending', 5), self.attempt(2, 'needs_review', 4)]
        result = self.overview('2026-09-21', attempts)
        self.assertEqual(result['assessed_answers'], 5)
        self.assertEqual(result['plan']['completed'], 3)
        self.assertEqual(result['plan']['remaining'], 3)
        self.assertEqual(result['topics'][0]['practised'], 1)
        self.assertEqual(result['streak'], 1)

    def test_disabled_and_unreviewed_questions_not_in_target(self):
        questions = [{'id':1,'enabled':False,'review_status':'accepted'}, {'id':2,'enabled':True,'review_status':'needs_review'}]
        result = self.overview('2026-09-21', questions=questions)
        self.assertEqual(result['plan']['total'],0)
        self.assertEqual(result['topics'][0]['mastery_state'],'not_practised')
        self.assertIsNone(result['topics'][0]['score_percent'])

    def test_disabled_pool_excluded_from_target(self):
        result = self.overview('2026-09-21', questions=[{'id':1, 'question_pool_id':9, 'enabled':True, 'review_status':'accepted'}], pools=[{'id':9,'enabled':False}])
        self.assertEqual(result['plan']['total'], 0)
        self.assertEqual(result['topics'][0]['available'], 0)
