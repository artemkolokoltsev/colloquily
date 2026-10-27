"""One learner action prepares uploaded material without bypassing quality gates."""
import time
import requests
from collections import defaultdict
from services.subject_workspace import workspace_for
from backend.services import workflows as flow
from backend.services.models import OllamaProvider
from services import processing_jobs, training_repository as training
from services.grounded_training import generate_grounded_questions
from services.local_models import subject_task_llm, merged_model_config
from services.question_pools import list_question_pools


def evidence_batches(units):
    """Stable topic/document batches with bounded context, covering every unit."""
    groups = defaultdict(list)
    for unit in units:
        if len(unit.get('content', '').split()) >= 8:
            groups[(unit.get('document_id'), unit.get('topic_id'))].append(unit)
    batches = []
    for group in groups.values():
        current, size = [], 0
        for unit in group:
            if current and (len(current) == 4 or size + len(unit['content']) > 12000):
                batches.append(current)
                current, size = [], 0
            current.append(unit)
            size += len(unit['content'])
        if current:
            batches.append(current)
    return batches


def prepare_exam(ident, progress):
    subject = flow.exam(ident)
    if merged_model_config(subject)['backend'] == 'ollama':
        status = OllamaProvider().status()
        if status['ollama'] != 'available':
            raise ValueError('Local AI needs setup. Open AI setup, finish installation, then try again.')
        from backend.services.models import setup_exam
        setup_exam(subject, progress, allow_downloads=False)
        subject = flow.exam(ident)
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
    current_evidence = training.accepted_evidence_map(ident)
    if not current_evidence:
        raise ValueError('We could not find clear study text in these files. Try a text-based PDF or check the passages under Advanced tools. Scanned PDFs may need text recognition first.')
    progress(message='Organising your study material…')
    flow.build_index(ident)
    disabled_pools = {p['id'] for p in list_question_pools(ident) if not p['enabled']}
    existing = training.list_questions(ident)
    batches = evidence_batches(current_evidence.values())
    current_ids = set(current_evidence)
    failures = []
    total = len(batches)
    processed = generated = 0
    coverage = []
    rejected_total = 0
    for evidence in batches:
        evidence_ids = {unit['id'] for unit in evidence}
        covered = [q for q in existing if q.get('review_status') == 'accepted' and q.get('enabled', True) and q.get('question_pool_id') not in disabled_pools and training.question_has_current_evidence(q, current_ids) and evidence_ids.intersection(q.get('evidence_ids', []))]
        target = min(6, max(2, sum(len(unit['content'].split()) for unit in evidence) // 100))
        needed = max(0, target - len(covered))
        entry = {'document_id': evidence[0].get('document_id'), 'topic_id': evidence[0].get('topic_id'),
                 'evidence_ids': sorted(evidence_ids), 'target': target, 'covered': len(covered), 'generated': 0}
        coverage.append(entry)
        if not needed:
            processed += 1
            continue
        progress(message=f'Preparing topics {processed + 1}/{total} · {generated} new questions', completed=processed, total=total)
        batch_rejected = 0
        def generation_progress(**values):
            nonlocal batch_rejected
            batch_rejected = values.get('rejected', 0)
            progress(**(values | {'accepted': generated + values.get('accepted', 0),
                                 'rejected': rejected_total + batch_rejected,
                                 'candidates': generated + rejected_total + values.get('candidates', 0)}))
        try:
            questions = generate_grounded_questions(subject, needed, llm_client=subject_task_llm(subject, 'question_generation'), evidence_units=evidence, progress=generation_progress, activate_validated=True)
            for question in questions:
                training.review_question(question['id'], 'accepted', subject_id=ident)
            existing.extend(questions)
            generated += len(questions)
            entry['generated'] = len(questions)
            if len(questions) < needed:
                failures.append(f'Only {len(questions)} of {needed} requested questions passed validation.')
        except requests.RequestException as exc:
            entry['error'] = str(exc)
            workspace = workspace_for(subject)
            workspace.atomic_json(workspace.folder('reports') / 'question-coverage.json', coverage)
            raise ValueError(str(exc)) from exc
        except ValueError as exc:
            failures.append(str(exc))
        processed += 1
        rejected_total += batch_rejected
        workspace = workspace_for(subject)
        workspace.atomic_json(workspace.folder('reports') / 'question-coverage.json', coverage)
    workspace = workspace_for(subject)
    workspace.atomic_json(workspace.folder('reports') / 'question-coverage.json', coverage)
    progress(completed=total, total=total, accepted=generated, rejected=rejected_total,
             candidates=generated + rejected_total)
    if failures and not generated:
        raise ValueError(f'{len(failures)} topic batches did not meet quality requirements. Validated questions were saved. Retry to continue; a stronger local model or clearer material may help. ' + failures[0])
    if not batches:
        raise ValueError('No sufficiently coherent study content found. Review extraction or add clearer materials.')
    progress(message='Validated questions are ready; some topic coverage remains incomplete' if failures else 'Your practice is ready')
    return {'questions': len([q for q in training.list_questions(ident, accepted_only=True) if q.get('question_pool_id') not in disabled_pools]),
            'coverage_status': 'partial' if failures else 'complete', 'limitations': failures}
