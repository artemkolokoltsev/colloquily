"""Exam-scoped learning overview and transparent deadline workload estimates."""
import json
import math
from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, datetime, timedelta

from services.database import _connect
from services.training_repository import list_questions
from services.progress import _attempt_rows
from services.question_pools import list_question_pools
from services.coverage import learner_mastery


def save_goal(user_id, subject_id, values):
    with closing(_connect()) as connection:
        connection.execute("""INSERT INTO learning_goals (user_id, subject_id, settings_json)
            VALUES (?, ?, ?) ON CONFLICT(user_id, subject_id)
            DO UPDATE SET settings_json=excluded.settings_json""",
            (user_id, subject_id, json.dumps(values)))
        connection.commit()


def learning_overview(user_id, subject_id, *, today=None):
    today = today or date.today()
    with closing(_connect()) as connection:
        row = connection.execute("SELECT settings_json FROM learning_goals WHERE user_id=? AND subject_id=?",
                                 (user_id, subject_id)).fetchone()
    goal = json.loads(row[0]) if row else {"exam_date": None, "repetitions": 3, "questions_per_session": 10}
    questions = list_questions(subject_id)
    disabled_pools = {p['id'] for p in list_question_pools(subject_id) if not p['enabled']}
    eligible = {q['id'] for q in questions if q['review_status'] == 'accepted' and q['enabled'] and q.get('question_pool_id') not in disabled_pools}
    names = {q['id']: q.get('topic_name') or 'Unassigned' for q in questions}
    grouped = defaultdict(list)
    for q in questions:
        grouped[names[q['id']]].append(q)
    assessed = []
    for a in _attempt_rows(user_id, subject_id):
        evaluation = json.loads(a['evaluation_json'] or '{}')
        if evaluation.get('status') in {'pending', 'needs_review', 'skipped'} or evaluation.get('score') is None:
            continue
        a['evaluation'] = evaluation
        assessed.append(a)
    counts = Counter(a['question_id'] for a in assessed)
    topics = []
    for name, items in sorted(grouped.items()):
        attempts = [a for a in assessed if names.get(a['question_id']) == name]
        score = sum(float(a['evaluation']['score']) for a in attempts) / len(attempts) if attempts else None
        topics.append({"name": name, "questions": len(items), "available": sum(q['id'] in eligible for q in items),
                       "practised": sum(counts[q['id']] > 0 for q in items), "attempts": len(attempts),
                       "score_percent": round(score * 20) if score is not None else None,
                       **learner_mastery(attempts)})
    days = Counter(datetime.fromisoformat(a['created_at']).astimezone().date().isoformat() for a in assessed)
    streak = 0
    cursor = today if days[today.isoformat()] else today - timedelta(days=1)
    while days[cursor.isoformat()]:
        streak += 1
        cursor -= timedelta(days=1)
    repetitions = goal['repetitions']
    total = len(eligible) * repetitions
    completed = sum(min(counts[q], repetitions) for q in eligible)
    remaining = total - completed
    deadline = date.fromisoformat(goal['exam_date']) if goal['exam_date'] else None
    days_left = (deadline - today).days if deadline else None
    # Include today and the exam day. Overdue plans do not silently invent future study days.
    study_days = days_left + 1 if days_left is not None and days_left >= 0 else 0
    daily = math.ceil(remaining / study_days) if study_days else 0
    schedule = []
    if study_days:
        for i in range(min(study_days, 14)):
            amount = remaining // study_days + int(i < remaining % study_days)
            schedule.append({"date": (today + timedelta(days=i)).isoformat(), "questions": amount,
                             "sessions": math.ceil(amount / goal['questions_per_session'])})
    return {"goal": goal, "topics": topics, "assessed_answers": len(assessed), "streak": streak,
            "today_answers": days[today.isoformat()], "activity": [
                {"date": (today - timedelta(days=13-i)).isoformat(), "answers": days[(today - timedelta(days=13-i)).isoformat()]}
                for i in range(14)],
            "plan": {"days_left": days_left, "study_days": study_days, "eligible_questions": len(eligible),
                     "total": total, "completed": completed, "remaining": remaining, "daily_questions": daily,
                     "daily_sessions": math.ceil(daily / goal['questions_per_session']),
                     "schedule": schedule, "overdue": days_left is not None and days_left < 0}}
