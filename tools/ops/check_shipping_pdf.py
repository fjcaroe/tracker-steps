"""Check native instruction PDF section boundaries and render pages for visual review."""
import argparse
import json
from pathlib import Path
import unicodedata
import pdfplumber
import pypdfium2

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('pdf',type=Path)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=True)
def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value or '').upper() if c.isalnum() and not unicodedata.combining(c))
with pdfplumber.open(a.pdf) as pdf:
    pages=[normalize(page.extract_text()) for page in pdf.pages]
    assert pages and all(pages), 'Empty page'
    assert all(abs(page.width-612)<1 and abs(page.height-792)<1 for page in pdf.pages), 'Expected portrait Letter'
    blocks={
        'DESGLOSE FLETE':('THC','Sistema de monitoreo','Documentación FEE - Destination'),
        'DOCUMENTACIÓN REQUERIDA':('D.U.S. 2do envío','Certificado de origen','SWB emisión en origen'),
        'INFORMACIÓN DE TRANSPORTE Y EMBARQUE':('BOOKING','THERMOS','VENTILACIÓN'),
        'FECHA ZARPE':('FECHA LLEGADA','STAKING','OPERADOR LOGÍSTICO'),
    }
    for heading,expected in blocks.items():
        containing=[text for text in pages if normalize(heading) in text]
        assert len(containing)==1 and all(normalize(s) in containing[0] for s in expected), 'Section split: '+heading
    for page in pages:
        assert page.count(normalize('DETALLES DEL PRODUCTO Y CARGA'))==page.count(normalize('CALIDAD')), 'Product block split'
    assert all('ESTADO' not in text for text in pages)
    if 'long' in a.pdf.name:
        assert any(normalize('OBSERVACIONES') in page and normalize('Observación de prueba 17') in page for page in pages), 'Observations split'
        assert any('PREPAID' in page for page in pages)
    red=0
    for page in pdf.pages:
        for char in page.chars:
            assert char['x0']>=0 and char['x1']<=page.width+1 and char['top']>=0 and char['bottom']<=page.height+1, 'Clipped text'
            color=char.get('non_stroking_color')
            if isinstance(color,(list,tuple)) and len(color)==3 and color[0]>.6 and color[0]>1.5*color[1] and color[0]>1.5*color[2]:
                red+=1
    assert red>50, 'Required red text absent'
document=pypdfium2.PdfDocument(a.pdf)
for index,page in enumerate(document):
    page.render(scale=1.5).to_pil().save(a.output/('page-%s.png'%(index+1)))
result={'pdf':a.pdf.name,'pages':len(pages),'section_boundaries':True,'red_characters':red,'portrait_letter':True,'text_inside_page':True}
(a.output/'checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('SHIPPING_PDF_OK '+json.dumps(result))
