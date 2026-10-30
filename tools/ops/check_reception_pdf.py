"""Render T141 native PDF pages and record visual review only after inspection."""
import argparse
import hashlib
import json
from pathlib import Path
import unicodedata
import pdfplumber
import pypdfium2


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text or '').upper() if c.isalnum() and not unicodedata.combining(c))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path)
    p.add_argument('--approve-visual',action='store_true',help='Use only after inspecting every generated page')
    a=p.parse_args();proof={}
    for path in sorted(a.folder.glob('*.pdf')):
        pages=[]
        with pdfplumber.open(path) as content:
            text=normalized(' '.join(page.extract_text() or '' for page in content.pages))
            assert all(normalized(label) in text for label in ('RECIBO DE RECEPCIÓN','Folio pallet','Kilos netos','Transportista','RUT chofer'))
            if 'long' in path.stem:
                assert len(content.pages)>=2
                for i in range(60):assert normalized('QA-141-LONG-%03d'%i) in text
            for i,page in enumerate(content.pages):
                chars=[c for c in page.chars if c['text'].strip()]
                assert chars and all(-1<=c['x0']<c['x1']<=page.width+1 and -1<=c['top']<c['bottom']<=page.height+1 for c in chars),str(path)
                pages.append({'page':i+1,'width':page.width,'height':page.height,'inside_page':True})
        document=pypdfium2.PdfDocument(path)
        for i in range(len(document)):
            output=path.with_name(path.stem+'-page-%d.png'%(i+1))
            document[i].render(scale=1.7).to_pil().save(output)
            pages[i]['image']=output.name
        proof[path.name]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pages':pages}
    assert proof,'No PDFs'
    (a.folder/'pdf-checks.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    if a.approve_visual:
        (a.folder/'visual-review.json').write_text(json.dumps({'reviewed':True,'files':proof},indent=2),encoding='utf-8')
    print(json.dumps({name:len(value['pages']) for name,value in proof.items()}))


if __name__=='__main__':main()
