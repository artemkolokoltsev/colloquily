"""Exam-scoped exercise drafts and local LaTeX submissions."""

from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from services import database as db
from backend.services.workflows import exam

MAX_PDF_BYTES = 100 * 1024 * 1024


def read_pdf(upload):
    if Path(upload.filename or "").suffix.lower() != ".pdf":
        raise ValueError("COURSE_PDF_REQUIRED")
    content = upload.file.read(MAX_PDF_BYTES + 1)
    if len(content) > MAX_PDF_BYTES:
        raise ValueError("SOURCE_TOO_LARGE")
    import pypdfium2 as pdfium
    from services.pdf_runtime import PDFIUM_LOCK

    try:
        with PDFIUM_LOCK, pdfium.PdfDocument(content) as pdf:
            pages = len(pdf)
            if not pages:
                raise ValueError("COURSE_PDF_INVALID")
    except (RuntimeError, ValueError) as exc:
        raise ValueError("COURSE_PDF_INVALID") from exc
    return content, pages


def now():
    return datetime.now(timezone.utc).isoformat()


def profile(subject_id):
    subject = exam(subject_id)
    with closing(db._connect()) as connection:
        row = connection.execute(
            "SELECT settings_json FROM submission_profiles WHERE subject_id=?",
            (subject_id,),
        ).fetchone()
    return (
        json.loads(row[0])
        if row
        else {
            "course_name": subject["name"],
            "semester": "",
            "authors": [{"name": "", "matrikelnummer": ""}],
        }
    )


def save_profile(subject_id, values):
    exam(subject_id)
    with closing(db._connect()) as connection:
        connection.execute(
            "INSERT INTO submission_profiles VALUES (?,?) ON CONFLICT(subject_id) DO UPDATE SET settings_json=excluded.settings_json",
            (subject_id, json.dumps(values)),
        )
        connection.commit()
    return values


def sheets(subject_id):
    exam(subject_id)
    with closing(db._connect()) as connection:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT id,title,filename,pages,revision,updated_at FROM exercise_sheets WHERE subject_id=? ORDER BY id",
                (subject_id,),
            )
        ]


def sheet(subject_id, sheet_id, *, include_pdf=False):
    exam(subject_id)
    columns = (
        "*"
        if include_pdf
        else "id,subject_id,title,filename,pages,latex,revision,updated_at"
    )
    with closing(db._connect()) as connection:
        row = connection.execute(
            f"SELECT {columns} FROM exercise_sheets WHERE subject_id=? AND id=?",
            (subject_id, sheet_id),
        ).fetchone()
    if not row:
        raise ValueError("EXERCISE_NOT_FOUND")
    return dict(row)


def upload_sheet(subject_id, upload):
    exam(subject_id)
    content, pages = read_pdf(upload)
    filename = Path((upload.filename or "exercise.pdf").replace("\\", "/")).name[:200]
    with closing(db._connect()) as connection:
        cursor = connection.execute(
            "INSERT INTO exercise_sheets(subject_id,title,filename,pages,source_pdf,latex,revision,updated_at) VALUES(?,?,?,?,?,?,1,?)",
            (
                subject_id,
                Path(filename).stem,
                filename,
                pages,
                content,
                "\\section*{Problem 1}\n\n% Write your solution here.\n",
                now(),
            ),
        )
        connection.commit()
        ident = cursor.lastrowid
    return sheet(subject_id, ident)


def save_sheet(subject_id, sheet_id, values):
    exam(subject_id)
    with closing(db._connect()) as connection:
        cursor = connection.execute(
            "UPDATE exercise_sheets SET title=?,latex=?,revision=revision+1,updated_at=? WHERE id=? AND subject_id=? AND revision=?",
            (
                values["title"],
                values["latex"],
                now(),
                sheet_id,
                subject_id,
                values["revision"],
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("EXERCISE_SAVE_CONFLICT")
        connection.commit()
    return sheet(subject_id, sheet_id)


def tex_escape(text):
    substitutions = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(substitutions.get(char, char) for char in text)


def submission_tex(subject_id, sheet_id, *, for_pdf=False):
    draft = sheet(subject_id, sheet_id)
    if for_pdf:
        from backend.services.solution_latex import validate_solution

        validate_solution(draft["latex"])
    details = profile(subject_id)
    authors = "\n".join(
        tex_escape(author["name"])
        + " & "
        + tex_escape(author["matrikelnummer"])
        + r" \\"
        for author in details["authors"]
        if author["name"] or author["matrikelnummer"]
    )
    return "\n".join(
        [
            r"\documentclass[11pt,a4paper]{article}",
            r"\usepackage[T1]{fontenc}",
            r"\usepackage[utf8]{inputenc}",
            r"\usepackage{amsmath,amssymb,amsthm}",
            r"\usepackage[margin=25mm]{geometry}",
            r"\setlength{\parindent}{0pt}",
            r"\setlength{\parskip}{6pt}",
            r"\begin{document}",
            r"\begin{center}",
            r"{\Large\bfseries " + tex_escape(details["course_name"]) + r"}\\[6pt]",
            tex_escape(details["semester"]) + r"\\[6pt]",
            r"{\large " + tex_escape(draft["title"]) + "}",
            r"\end{center}",
            r"\begin{tabular}{ll}",
            r"\textbf{Name} & \textbf{Matrikelnummer} \\",
            authors,
            r"\end{tabular}",
            r"\medskip\hrule\medskip",
            draft["latex"],
            r"\end{document}",
            "",
        ]
    )


def latex_engine():
    found = shutil.which("pdflatex")
    if found:
        return found
    # GUI applications on macOS do not inherit the login shell's TeX PATH.
    mac = Path("/Library/TeX/texbin/pdflatex")
    return str(mac) if mac.is_file() else None


def compile_pdf(source):
    engine = latex_engine()
    if not engine:
        raise ValueError("LATEX_UNAVAILABLE")
    with tempfile.TemporaryDirectory(prefix="colloquily-latex-") as directory:
        root = Path(directory)
        (root / "submission.tex").write_text(source, encoding="utf-8")
        env = {
            **os.environ,
            "openin_any": "p",
            "openout_any": "p",
            "shell_escape": "f",
            "TEXMFOUTPUT": directory,
        }
        try:
            for _ in range(2):
                result = subprocess.run(
                    [
                        engine,
                        "-no-shell-escape",
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        "-file-line-error",
                        "submission.tex",
                    ],
                    cwd=directory,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=30,
                    check=False,
                )
                if result.returncode:
                    # The compiler log identifies the offending line; never return a partial PDF.
                    log = result.stdout.decode("utf-8", errors="replace")
                    raise ValueError("LATEX_COMPILE_FAILED\n" + log[-3000:])
        except subprocess.TimeoutExpired as exc:
            raise ValueError("LATEX_TIMEOUT") from exc
        return (root / "submission.pdf").read_bytes()
