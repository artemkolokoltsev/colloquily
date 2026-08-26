from __future__ import annotations

import logging
from pathlib import Path

import fitz

import config


LOGGER = logging.getLogger(__name__)


def extract_embedded_images(pdf_path: str, page_number: int) -> list[dict]:
    doc_name = Path(pdf_path).stem
    output_dir = Path(config.IMAGE_CACHE_DIR) / doc_name
    output_dir.mkdir(parents=True, exist_ok=True)
    images_metadata: list[dict] = []

    with fitz.open(pdf_path) as doc:
        page = doc.load_page(page_number - 1)
        for index, image_info in enumerate(page.get_images(full=True), start=1):
            xref = image_info[0]
            extracted = doc.extract_image(xref)
            extension = extracted.get("ext", "png")
            image_id = f"{doc_name}_p{page_number}_img{index}"
            image_path = output_dir / f"{image_id}.{extension}"
            image_path.write_bytes(extracted["image"])
            metadata = {
                "image_id": image_id,
                "doc_name": f"{doc_name}.pdf",
                "page_number": page_number,
                "image_path": str(image_path),
                "width": extracted.get("width"),
                "height": extracted.get("height"),
            }
            images_metadata.append(metadata)
            LOGGER.info("Embedded image extracted", extra=metadata)
    return images_metadata

