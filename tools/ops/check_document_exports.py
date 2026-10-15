"""Render native export PDFs and reject out-of-page text before visual review."""
import argparse
import json
from pathlib import Path
import fitz

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('folder', type=Path)
a = p.parse_args()
results = {}
for path in sorted(a.folder.rglob('*.pdf')):
    document = fitz.open(path)
    assert len(document) > 0
    pages = []
    for index, page in enumerate(document):
        assert sorted(round(n) for n in (page.rect.width, page.rect.height)) == [612, 792]
        spans = [span for block in page.get_text('dict')['blocks'] if block['type'] == 0
                 for line in block['lines'] for span in line['spans'] if span['text'].strip()]
        assert spans
        assert all(-1 <= s['bbox'][0] < s['bbox'][2] <= page.rect.width + 1
                   and -1 <= s['bbox'][1] < s['bbox'][3] <= page.rect.height + 1 for s in spans), str(path)
        output = path.with_name(path.stem + '-page-%d.png' % (index + 1))
        page.get_pixmap(matrix=fitz.Matrix(1.3, 1.3)).save(output)
        pages.append({'page': index + 1, 'image': str(output), 'text_inside_page': True})
    results[str(path.relative_to(a.folder))] = {'pages': pages}
(a.folder/'pdf-checks.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps({name:len(value['pages']) for name,value in results.items()}))
