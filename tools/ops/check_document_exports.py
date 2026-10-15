"""Render native export PDFs and reject out-of-page text before visual review."""
import argparse
import json
from pathlib import Path
import pdfplumber
import pypdfium2

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('folder', type=Path)
a = p.parse_args()
results = {}
for path in sorted(a.folder.rglob('*.pdf')):
    document = pypdfium2.PdfDocument(path)
    assert len(document) > 0
    pages = []
    with pdfplumber.open(path) as content:
        for index, page in enumerate(content.pages):
            assert sorted(round(n) for n in (page.width, page.height)) == [612, 792]
            chars = [char for char in page.chars if char['text'].strip()]
            assert chars
            assert all(-1 <= c['x0'] < c['x1'] <= page.width + 1
                       and -1 <= c['top'] < c['bottom'] <= page.height + 1 for c in chars), str(path)
            output = path.with_name(path.stem + '-page-%d.png' % (index + 1))
            document[index].render(scale=1.3).to_pil().save(output)
            pages.append({'page': index + 1, 'image': str(output), 'text_inside_page': True})
    results[str(path.relative_to(a.folder))] = {'pages': pages}
(a.folder/'pdf-checks.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps({name:len(value['pages']) for name,value in results.items()}))
