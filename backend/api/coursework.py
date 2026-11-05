"""HTTP contracts for lecture revisions and exercise submissions."""

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response

from backend.models.api import SubmissionProfile, ExerciseInput
from backend.services import coursework, lecture_scripts

router = APIRouter(prefix="/exams/{ident}")


@router.get("/lecture-script")
def script(ident: int):
    return {
        "current": lecture_scripts.current(ident),
        "revisions": lecture_scripts.revisions(ident),
    }


@router.put("/lecture-script")
def replace_script(
    ident: int, file: UploadFile = File(...), document_id: int | None = Form(None)
):
    return lecture_scripts.replace(ident, file, document_id)


@router.get("/lecture-script/revisions/{number}")
def script_revision(ident: int, number: int):
    return Response(
        lecture_scripts.revision(ident, number)["content"], media_type="application/pdf"
    )


@router.get("/lecture-script/revisions/{number}/notes")
def script_notes(ident: int, number: int):
    import json

    return json.loads(lecture_scripts.revision(ident, number)["notes_json"])


@router.get("/submission-profile")
def profile(ident: int):
    return coursework.profile(ident)


@router.put("/submission-profile")
def save_profile(ident: int, body: SubmissionProfile):
    return coursework.save_profile(ident, body.model_dump())


@router.get("/exercises")
def exercises(ident: int):
    return {
        "sheets": coursework.sheets(ident),
        "pdf_export_available": bool(coursework.latex_engine()),
    }


@router.post("/exercises", status_code=201)
def upload_exercise(ident: int, file: UploadFile = File(...)):
    return coursework.upload_sheet(ident, file)


@router.get("/exercises/{sheet_id}")
def exercise(ident: int, sheet_id: int):
    return coursework.sheet(ident, sheet_id)


@router.put("/exercises/{sheet_id}")
def save_exercise(ident: int, sheet_id: int, body: ExerciseInput):
    return coursework.save_sheet(ident, sheet_id, body.model_dump())


@router.get("/exercises/{sheet_id}/source")
def exercise_source(ident: int, sheet_id: int):
    return Response(
        coursework.sheet(ident, sheet_id, include_pdf=True)["source_pdf"],
        media_type="application/pdf",
    )


@router.get("/exercises/{sheet_id}/tex")
def export_tex(ident: int, sheet_id: int):
    return Response(
        coursework.submission_tex(ident, sheet_id),
        media_type="application/x-tex",
        headers={"Content-Disposition": 'attachment; filename="submission.tex"'},
    )


@router.post("/exercises/{sheet_id}/pdf")
def export_pdf(ident: int, sheet_id: int):
    return Response(
        coursework.compile_pdf(
            coursework.submission_tex(ident, sheet_id, for_pdf=True)
        ),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="submission.pdf"'},
    )
