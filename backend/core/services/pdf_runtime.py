"""All PDFium calls share one lock: PDFium is not thread-safe."""
from threading import RLock
PDFIUM_LOCK = RLock()
