"""Small frozen-runtime check, executed automatically after packaging."""


def run():
    import json
    import numpy as np
    from services.synthetic_pdf import synthetic_pdf
    from pathlib import Path
    from fastapi.testclient import TestClient
    from backend.main import app
    from services.subject_workspace import workspace_for
    from services.quality_pipeline import process_subject
    from services.subject_index import SubjectIndex
    from services.prompt_templates import PROMPT_ROOT
    from services.knowledge_repository import accepted_units, review_unit
    import sys

    if getattr(sys, "frozen", False):
        licenses = Path(sys._MEIPASS) / "licenses"
        for name in (
            "LICENSE",
            "NOTICE",
            "THIRD_PARTY_NOTICES.txt",
            "FRONTEND_NOTICES.txt",
            "RUST_NOTICES.txt",
            "MPL-SOURCES.zip",
        ):
            assert (licenses / name).is_file(), (
                f"Missing redistributed notice/source: {name}"
            )

    class Embedder:
        def embed(self, texts):
            return np.asarray(
                [[1.0, len(text) / 1000.0, 0.5] for text in texts], dtype=np.float32
            )

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        response = client.post("/api/exams", json={"name": "Frozen runtime check"})
        assert response.status_code == 201, response.text
        exam = response.json()
        raw = workspace_for(exam).folder("raw")
        content = "A network protocol defines message structure and the actions used by devices to exchange information."
        (raw / "notes.md").write_text("# Networks\n\n" + content, encoding="utf-8")
        synthetic_pdf([[(72, 72, content)]], raw / "notes.pdf")
        result = process_subject(exam["id"], mode="deterministic")
        assert not result["failed"], result
        index = SubjectIndex(exam["id"], embedder=Embedder())
        assert index.build()["indexed_units"] > 0
        loaded = SubjectIndex(exam["id"], embedder=Embedder())
        assert loaded.load()
        assert loaded.search("network protocol")
        for unit in accepted_units(exam["id"]):
            review_unit(unit["id"], "rejected", subject_id=exam["id"])
        assert loaded.search("network protocol") == []
        assert index.build()["indexed_units"] == 0
        assert not SubjectIndex(exam["id"], embedder=Embedder()).load()
        assert (PROMPT_ROOT / "training.json").is_file(), PROMPT_ROOT
        assert json.loads((PROMPT_ROOT / "training.json").read_text())
        review = client.get(f"/api/exams/{exam['id']}/review-page?limit=1")
        assert review.status_code == 200, review.text
        assert len(review.json()["items"]) == 1
        assert "raw_content" not in review.json()["items"][0]
        _check_coursework(client)
    print(
        "Frozen backend self-test passed: API, PDF/Markdown, SQLite, FAISS, review filtering, prompts."
    )


def _check_coursework(client):
    """Exercise new routes/imports inside every target-native frozen build."""
    from services.synthetic_pdf import synthetic_pdf

    exam = client.post("/api/exams", json={"name": "Frozen coursework"}).json()["id"]
    prefix = f"/api/exams/{exam}"
    original = synthetic_pdf([[(40, 70, "Exercise: prove permutation invariance.")]])
    revised = synthetic_pdf(
        [[(40, 70, "Updated lecture script: permutation equivariance.")]]
    )
    first = client.put(
        prefix + "/lecture-script", files={"file": ("lecture-5.pdf", original)}
    )
    assert first.status_code == 200, first.text
    second = client.put(
        prefix + "/lecture-script", files={"file": ("lecture-6.pdf", revised)}
    )
    assert second.status_code == 200, second.text
    assert first.json()["document_id"] == second.json()["document_id"]
    assert second.json()["revision"] == 2
    assert client.get(prefix + "/lecture-script/revisions/1").content == original
    response = client.post(
        prefix + "/exercises", files={"file": ("exercise.pdf", original)}
    )
    assert response.status_code == 201, response.text
    path = prefix + "/exercises/" + str(response.json()["id"])
    saved = client.put(
        path,
        json={
            "title": "Exercise 1",
            "latex": r"\section*{Problem 1} $x^2$",
            "revision": 1,
        },
    )
    assert saved.status_code == 200, saved.text
    assert client.get(path + "/source").content == original
    assert r"\section*{Problem 1}" in client.get(path + "/tex").text
    print(
        "Frozen coursework passed: script replacement, revision history, exercise storage and LaTeX export."
    )
