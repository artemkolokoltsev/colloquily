from __future__ import annotations
import os
import re
import pypdfium2 as pdfium
import config
from services.pdf_runtime import PDFIUM_LOCK

def _block_type_guess(text):
    if re.match(r'^[-*•]\s+', text): return 'bullet_group'
    if re.match(r'^\d+[.)]\s+', text): return 'numbered_list'
    if re.search(r'[=±∑∆√]', text): return 'formula'
    if len(text) <= 90 and not text.endswith('.'): return 'heading_candidate'
    if '|' in text: return 'table_like'
    return 'text'

class PDFiumParser:
    name = 'pdfium'

    def parse(self, path, profile=None):
        pages = []
        with PDFIUM_LOCK, pdfium.PdfDocument(path) as document:
            for page_index in range(len(document)):
                page = document[page_index]
                try:
                    width, height = page.get_size()
                    textpage = page.get_textpage()
                    try:
                        raw = textpage.get_text_range().replace('\r\n', '\n').strip()
                        blocks = []
                        if config.ENABLE_BLOCK_EXTRACTION:
                            rectangles = [textpage.get_rect(i) for i in range(textpage.count_rects())]
                            rectangles.sort(key=lambda box: (-round(box[3], 1), round(box[0], 1)))
                            for rectangle in rectangles:
                                left, bottom, right, top = rectangle
                                text = textpage.get_text_bounded(left=left-.1, bottom=bottom-.1, right=right+.1, top=top+.1).replace('\r\n', '\n').strip()
                                if not text: continue
                                kind = _block_type_guess(text)
                                index = len(blocks)
                                blocks.append({'block_index': index, 'text': text, 'block_type_guess': kind,
                                    'bbox': [left, height-top, right, height-bottom], 'line_count': len(text.splitlines()),
                                    'is_heading_candidate': kind == 'heading_candidate', 'is_bullet_group': kind == 'bullet_group',
                                    'is_table_like': kind == 'table_like', 'is_formula_like': kind == 'formula',
                                    'reading_order_index': index, 'metadata': {'source': self.name, 'block_no': index}})
                        pages.append({'page_number': page_index+1, 'raw_text': raw,
                            'text_blocks': blocks, 'reading_order_index': [b['block_index'] for b in blocks],
                            'parser_used': self.name, 'parser_confidence': .82 if raw else .2,
                            'metadata': {'page_rect': [0., 0., width, height], 'source_path': str(path)}})
                    finally:
                        textpage.close()
                finally:
                    page.close()
        return {'filename': os.path.basename(path), 'source_path': str(path), 'page_count': len(pages),
            'pages': pages, 'parser_used': self.name, 'parser_profile': profile or config.PARSER_PROFILE,
            'fallback_used': False, 'blocks_count': sum(len(page['text_blocks']) for page in pages),
            'metadata': {'parser_backend': self.name}}
