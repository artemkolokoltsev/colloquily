"""Collect actual frozen Python licenses, including PDFium's native notices."""
import importlib.metadata as metadata
import json
from pathlib import Path
import re

FORBIDDEN = {'pymupdf', 'pymupdf4llm', 'marker-pdf', 'surya-ocr'}

def collect_notices(modules, destination):
    mapping = metadata.packages_distributions()
    names = {'pyinstaller', 'pypdfium2'}
    for module in modules:
        names.update(mapping.get(module.split('.')[0], []))
    entries = []
    notices = ['Colloquily third-party runtime notices\n', 'Python interpreter: Python Software Foundation License. See https://docs.python.org/3/license.html\n']
    for name in sorted(names, key=str.lower):
        normalized = name.lower().replace('_','-')
        if normalized in FORBIDDEN:
            raise RuntimeError(f'Forbidden runtime dependency: {name}')
        distribution = metadata.distribution(name)
        license_name = distribution.metadata.get('License-Expression') or distribution.metadata.get('License') or '; '.join(value for value in distribution.metadata.get_all('Classifier', []) if value.startswith('License ::'))
        if re.search(r'AGPL|Affero', license_name, re.I):
            raise RuntimeError(f'AGPL runtime dependency: {name}')
        entries.append({'name': name, 'version': distribution.version, 'license': license_name})
        notices.append(f'\n{name} {distribution.version}\nDeclared license: {license_name}\n')
        found = False
        for relative in distribution.files or []:
            if not any(token in str(relative).lower() for token in ('license', 'notice', 'copying')):
                continue
            source = distribution.locate_file(relative)
            if not source.is_file(): continue
            try: text = source.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError): continue
            # GPLv3 section 13 mentions Affero but does not make NumPy/GCC
            # libraries AGPL. Reject actual license headings/identifiers.
            if re.search(r'^\s*GNU AFFERO GENERAL PUBLIC LICENSE\s*$|SPDX-License-Identifier:\s*AGPL-[123]', text, re.I | re.M):
                raise RuntimeError(f'AGPL license in {name}: {relative}')
            notices.append(f'\n--- {name}: {relative.name} ---\n{text}\n')
            found = True
        if not found:
            notices.append('License metadata provided above; upstream project URL: ' + str(distribution.metadata.get('Home-page', '')) + '\n')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    (destination/'THIRD_PARTY_NOTICES.txt').write_text('\n'.join(notices), encoding='utf-8')
    (destination/'runtime-dependencies.json').write_text(json.dumps(entries, indent=2)+'\n', encoding='utf-8')
    (destination/'runtime-audit.txt').write_text('\n'.join(f'{item["name"]}=={item["version"]}' for item in entries if item['name'].lower() != 'pyinstaller')+'\n', encoding='utf-8')
    return destination
