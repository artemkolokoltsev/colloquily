"""Deterministic PDF creation for isolated runtime self-tests and developer tools."""
from io import BytesIO
from textwrap import wrap
from reportlab.pdfgen import canvas

def synthetic_pdf(pages: list[list[tuple[float, float, str]]], destination=None) -> bytes:
    output = BytesIO()
    document = canvas.Canvas(output, pagesize=(595, 842), invariant=True)
    for lines in pages:
        for x, top, text in lines:
            for number, line in enumerate(wrap(text, width=75) or ['']):
                document.drawString(x, 842-top-number*15, line)
        document.showPage()
    document.save()
    content = output.getvalue()
    if destination is not None:
        from pathlib import Path
        Path(destination).write_bytes(content)
    return content
