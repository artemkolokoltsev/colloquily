import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from reportlab.pdfgen import canvas
from PIL import Image
import config
from services.pdf_parsers.pdfium_parser import PDFiumParser
from services.images.page_renderer import render_page_to_image
from services.images.image_extractor import extract_embedded_images

class PDFiumRegressionTests(unittest.TestCase):
    def test_text_coordinates_render_images_and_parallel_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / 'synthetic.png'
            Image.new('RGB', (80,40), '#3478db').save(image)
            source = root / 'synthetic.pdf'
            document = canvas.Canvas(str(source), pagesize=(595,842))
            document.drawString(72,770,'Prüfung: Größe und Ähnlichkeit')
            document.drawString(72,735,'Reliable protocols retransmit lost packets.')
            document.drawImage(str(image),72,600,width=80,height=40)
            document.showPage()
            document.drawString(72,770,'Second page: routing and addresses')
            document.save()
            with ThreadPoolExecutor(max_workers=4) as workers:
                results = list(workers.map(lambda _: PDFiumParser().parse(str(source)), range(8)))
            self.assertTrue(all(result['page_count'] == 2 for result in results))
            first = results[0]['pages'][0]
            self.assertIn('Prüfung', first['raw_text'])
            self.assertTrue(first['text_blocks'])
            self.assertTrue(all(0 <= box['bbox'][1] < box['bbox'][3] <= 842 for box in first['text_blocks']))
            with patch.object(config, 'PAGE_RENDER_DIR', str(root/'renders')), patch.object(config, 'IMAGE_CACHE_DIR', str(root/'images')):
                rendered = Path(render_page_to_image(str(source),1))
                with Image.open(rendered) as output:
                    self.assertEqual(output.size, (1190,1684))
                images = extract_embedded_images(str(source),1)
                self.assertEqual(len(images),1)
                self.assertTrue(Path(images[0]['image_path']).exists())

    def test_invalid_pdf_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'invalid.pdf'
            source.write_bytes(b'not a PDF')
            with self.assertRaises(RuntimeError):
                PDFiumParser().parse(str(source))
