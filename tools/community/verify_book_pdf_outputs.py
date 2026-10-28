"""Check private synthetic PDFs from real Odoo report routes, then rasterize them.

This validates report transport/layout evidence, not Chilean payroll or CSV rules.
Run with pypdf and a local Poppler pdftoppm executable; no database connection.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unicodedata

from pypdf import PdfReader


def compact(value):
    return ''.join(unicodedata.normalize('NFKC', value).split())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--renderer', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {'synthetic_only': True, 'database_access': False,
              'financial_certified': False, 'reports': []}
    for mode in ('community', 'cerro-reference'):
        directory = args.evidence / mode / 'pdf-evidence'
        proofs = json.loads((directory / 'pdf-proof.json').read_text(encoding='utf-8'))
        assert len(proofs) == 2
        assert {row['report'] for row in proofs} == {'consolidated_book', 'employee_sheets'}
        for proof in proofs:
            name = proof['report']
            path = directory / (name + '.pdf')
            blob = path.read_bytes()
            assert blob.startswith(b'%PDF-') and hashlib.sha256(blob).hexdigest() == proof['sha256']
            assert proof['normal_actor'] and proof['single_audit'] and proof['history_preserved']
            reader = PdfReader(path)
            assert len(reader.pages) == proof['pages'] > 0
            text = '\n'.join(page.extract_text() for page in reader.pages)
            assert compact('Private API employee') in compact(text), (mode, name, 'employee missing')
            assert re.search(r'(?<!\d)125(?!\d)', text), (mode, name, 'amount missing')
            assert re.search(r'(?<!\d)0(?!\d)', text), (mode, name, 'explicit zero missing')
            label = 'Total general' if name == 'consolidated_book' else 'No constituye liquidaci\u00f3n'
            assert compact(label) in compact(text), (mode, name, 'report label missing')
            dimensions = (1008, 612) if name == 'consolidated_book' else (595, 842)
            fonts=set()
            for page in reader.pages:
                for font in page['/Resources'].get('/Font',{}).get_object().values():
                    fonts.add(str(font.get_object().get('/BaseFont','')))
                assert abs(float(page.mediabox.width) - dimensions[0]) < 2
                assert abs(float(page.mediabox.height) - dimensions[1]) < 2
            assert fonts and all('DejaVuSans' in font for font in fonts), (mode,name,fonts)
            for number in range(1, len(reader.pages) + 1):
                prefix = directory / (name + '-page-' + str(number))
                subprocess.run([str(args.renderer), '-f', str(number), '-l', str(number),
                                '-singlefile', '-scale-to', '1800', '-png', str(path), str(prefix)], check=True)
                assert prefix.with_suffix('.png').stat().st_size > 1000
            result['reports'].append({'mode': mode, 'report': name, 'pages': len(reader.pages),
                                      'sha256': proof['sha256'], 'local_fonts':sorted(fonts), 'text_and_dimensions_checked': True})
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
