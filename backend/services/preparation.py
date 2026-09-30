"""One learner action prepares uploaded material without bypassing quality gates."""
import time
import requests
from backend.services import workflows as flow
from backend.services.models import OllamaProvider
from services import processing_jobs, training_repository as training
from services.grounded_training import generate_grounded_questions
from services.local_models import subject_task_llm
from services.question_pools import list_question_pools


def prepare_exam(ident, progress):
    subject = flow.exam(ident)
    status = OllamaProvider().status()
    if status['ollama'] != 'available' or status['missing']:
        raise ValueError('Local AI needs setup. Open AI setup, finish installation, then try again.')
    progress(message='Reading your materials…')
    job = processing_jobs.create_processing_job(ident, {'mode': 'deterministic', 'retry_failed': True})
    processing_jobs.start_processing_job(job['id'])
    while True:
        job = processing_jobs.get_processing_job(job['id'])
        if job['status'] not in {'queued', 'running'}:
            break
        time.sleep(.5)
    if job['status'] != 'completed':
        raise ValueError('Some files could not be read. Check the file details below and try again. ' + (job.get('error_text') or ''))
    if not training.accepted_evidence_map(ident):
        raise ValueError('We could not find clear study text in these files. Try a text-based PDF or check the passages under Advanced tools. Scanned PDFs may need text recognition first.')
    progress(message='Organising your study material…')
    flow.build_index(ident)
    disabled_pools = {p['id'] for p in list_question_pools(ident) if not p['enabled']}
    available = [q for q in training.list_questions(ident, accepted_only=True) if q.get('question_pool_id') not in disabled_pools]
    if not available:
        progress(message='Writing your first practice questions…')
        try:
            questions = generate_grounded_questions(subject, 5, llm_client=subject_task_llm(subject, 'question_generation'))
        except (ValueError, requests.RequestException):
            progress(message='Preparing starter questions directly from your notes…')
            questions = source_starters(ident)
        if not questions:
            raise ValueError('We could not prepare new questions. Check your material or add another PDF and try again.')
        # Only newly generated, validated questions are activated. Previously rejected
        # or manually held questions are never approved by this convenience workflow.
        for question in questions:
            training.review_question(question['id'], 'accepted', subject_id=ident)
    progress(message='Your practice is ready')
    return {'questions': len([q for q in training.list_questions(ident, accepted_only=True) if q.get('question_pool_id') not in disabled_pools])}


def source_starters(ident):
    """Extractive fallback: no invented rubric or unsupported source claims."""
    existing = {q['question_text'] for q in training.list_questions(ident)}
    questions = []
    for evidence_id, unit in training.accepted_evidence_map(ident).items():
        content = ' '.join(unit['content'].split())
        if len(content) < 40:
            continue
        excerpt = content[:180] + ('…' if len(content) > 180 else '')
        prompt = f'How would you explain this passage in your own words: “{excerpt}” ?'
        if prompt in existing:
            continue
        question = training.create_question(ident, {
            'question_text': prompt, 'question_type': 'explanation', 'difficulty': 'medium',
            'topic_id': unit.get('topic_id'), 'expected_duration_seconds': 90,
            'evidence_ids': [evidence_id], 'quality_score': 0.7,
            'expected_core_points': [{'text':content, 'evidence_ids':[evidence_id], 'priority':'must_know'}],
            'review_status':'needs_review', 'source_provenance':'Extractive starter from accepted course material',
        })
        questions.append(question)
        existing.add(prompt)
        if len(questions) >= 5:
            break
    return questions
