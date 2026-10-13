from __future__ import annotations

import logging
from pathlib import Path

import pypdfium2 as pdfium
from services.pdf_runtime import PDFIUM_LOCK

import config


LOGGER = logging.getLogger(__name__)


def extract_embedded_images(pdf_path: str, page_number: int) -> list[dict]:
    doc_name = Path(pdf_path).stem
    output_dir = Path(config.IMAGE_CACHE_DIR) / doc_name
    output_dir.mkdir(parents=True, exist_ok=True)
    images_metadata: list[dict] = []

    with PDFIUM_LOCK, pdfium.PdfDocument(pdf_path) as doc:
        page = doc[page_number - 1]
        try:
            for index, image_object in enumerate(page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE]), start=1):
                image_id = f'{doc_name}_p{page_number}_img{index}'
                image_path = output_dir / f'{image_id}.png'
                bitmap = image_object.get_bitmap(render=True)
                try:
                    image = bitmap.to_pil()
                    image.save(image_path)
                    metadata = {'image_id': image_id, 'doc_name': f'{doc_name}.pdf', 'page_number': page_number,
                        'image_path': str(image_path), 'width': image.width, 'height': image.height}
                    image.close()
                    images_metadata.append(metadata)
                    LOGGER.info('Embedded image extracted', extra=metadata)
                finally:
                    bitmap.close()
        finally:
            page.close()
    return images_metadata

