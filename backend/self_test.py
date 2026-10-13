"""Small frozen-runtime check, executed automatically after packaging."""
def run():
    import json
    import numpy as np
    import fitz
    from pathlib import Path
    from fastapi.testclient import TestClient
    from backend.main import app
    from services.subject_workspace import workspace_for
    from services.quality_pipeline import process_subject
    from services.subject_index import SubjectIndex
    from services.prompt_templates import PROMPT_ROOT
    from services.knowledge_repository import accepted_units, review_unit

    class Embedder:
        def embed(self, texts):
            return np.asarray([[1.0, len(text) / 1000.0, .5] for text in texts], dtype=np.float32)

    with TestClient(app) as client:
        assert client.get('/api/health').status_code == 200
        response = client.post('/api/exams', json={'name': 'Frozen runtime check'})
        assert response.status_code == 201, response.text
        exam = response.json()
        raw = workspace_for(exam).folder('raw')
        content = 'A network protocol defines message structure and the actions used by devices to exchange information.'
        (raw / 'notes.md').write_text('# Networks\n\n' + content, encoding='utf-8')
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), content)
        doc.save(raw / 'notes.pdf')
        doc.close()
        result = process_subject(exam['id'], mode='deterministic')
        assert not result['failed'], result
        index = SubjectIndex(exam['id'], embedder=Embedder())
        assert index.build()['indexed_units'] > 0
        loaded = SubjectIndex(exam['id'], embedder=Embedder())
        assert loaded.load()
        assert loaded.search('network protocol')
        for unit in accepted_units(exam['id']):
            review_unit(unit['id'], 'rejected', subject_id=exam['id'])
        assert loaded.search('network protocol') == []
        assert index.build()['indexed_units'] == 0
        assert not SubjectIndex(exam['id'], embedder=Embedder()).load()
        assert (PROMPT_ROOT / 'training.json').is_file(), PROMPT_ROOT
        assert json.loads((PROMPT_ROOT / 'training.json').read_text())
    print('Frozen backend self-test passed: API, PDF/Markdown, SQLite, FAISS, review filtering, prompts.')
