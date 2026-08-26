from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from services.database import create_subject, init_db
from services.knowledge_repository import accepted_units, list_review_units
from services.local_models import default_model_config, subject_task_llm
from services.quality_pipeline import process_subject
from services.subject_workspace import workspace_for


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="oral-exam-trainer-smoke-") as tmpdir:
        original_db, original_subjects = config.DB_PATH, config.SUBJECTS_DIR
        config.DB_PATH = os.path.join(tmpdir, "app.db")
        config.SUBJECTS_DIR = os.path.join(tmpdir, "subjects")
        try:
            init_db()
            model_config = default_model_config()
            model_config["task_models"] = {task: "llama3:latest" for task in model_config["task_models"]}
            model_config["batch_size"] = 1
            subject = create_subject(
                "Synthetic Learning Technologies",
                language="en",
                local_llm_config=model_config,
                embedding_config={"backend": "st", "model": config.ST_EMBED_MODEL},
            )
            raw_path = workspace_for(subject).folder("raw") / "learning_theory.md"
            raw_path.write_text(
                "Behaviorism explains observable learning as a change in behavior shaped by reinforcement and environmental consequences.",
                encoding="utf-8",
            )
            client = subject_task_llm(subject, "cleaning")
            result = process_subject(
                subject["id"], cleanup_generate=client.generate,
                local_model=client.model_name,
            )
            payload = {
                "model": client.model_name,
                "processing": result,
                "accepted_units": len(accepted_units(subject["id"])),
                "review_units": len(list_review_units(subject["id"])),
                "raw_unchanged": raw_path.read_text(encoding="utf-8").startswith("Behaviorism explains"),
            }
            print(json.dumps(payload, indent=2))
            if result["failed"] or not payload["raw_unchanged"] or payload["review_units"] < 1:
                raise SystemExit(1)
        finally:
            config.DB_PATH, config.SUBJECTS_DIR = original_db, original_subjects


if __name__ == "__main__":
    main()
