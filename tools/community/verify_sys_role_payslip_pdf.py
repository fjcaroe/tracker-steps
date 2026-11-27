"""Verify payslip downloads from both real operator roles without publishing the private PDFs."""
import argparse
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re

import pymupdf


WAGE = re.compile(r'salario del contrato(?:\s*\([^)]*\))?\s*:?\s*\$\s*(-?\d[\d.]*)', re.I)
FONTS = {'Lato-Regular','Lato-Bold'}


def check(condition, message):
    if not condition:
        raise ValueError(message)


def pdf(path):
    with pymupdf.open(path) as document:
        fonts, pixels, texts, boxes = set(), [], [], []
        for page in document:
            fonts.update(font[3].split('+')[-1] for font in page.get_fonts())
            pixels.append(sha256(page.get_pixmap(dpi=96, colorspace=pymupdf.csRGB, alpha=False).samples).hexdigest())
            texts.append(' '.join(page.get_text().split()))
            boxes.append([round(page.rect.width,2),round(page.rect.height,2)])
    return {'pixels':pixels,'size':boxes,'text':' '.join(texts),'fonts':fonts}


def wage(text):
    values = WAGE.findall(text)
    check(len(values) == 1,'The printable contract wage could not be identified')
    return Decimal(values[0].replace('.',''))


def printed_table(table, created):
    # The two QA transactions consume different document numbers for a newly created slip.
    return [row if not created or not row or row[0].strip().rstrip(':') != 'Referencia' else [row[0], *row[2:]]
            for row in table]


def run(folder, version):
    payroll = {'existing':0,'new':0,'identical_old_amount_rows':0,'one_page':0,'contract_wages':0,'downloads':0}
    for phase, key in (('old','existing'),('new','new')):
        native = folder/('native-'+phase+'-2')
        old = folder/('community-'+phase+('-2' if phase=='old' else '-1'))
        release = folder/(version+'-'+phase)
        native_receipt, current = [json.loads((path/'receipt.json').read_bytes()) for path in (native,release)]
        check(len(native_receipt['documents']) == len(current['documents']) == (10 if phase=='old' else 2),
              'Incomplete reference role workload')
        check(native_receipt['renderer'] == current['renderer'],'Physical renderers differ')
        check(current['original_attachments'] == 8, 'Missing physical historic PDFs')
        files = sorted(release.glob(phase+'-*.json'))
        check(len(files) == len(current['documents']), 'Missing individual salary evidence')
        for source, actual, f in zip(native_receipt['documents'],current['documents'],files):
            check(all(source[k]==actual[k] for k in ('action','actor','form','scope')) and actual['button_type']=='ir.actions.report',
                  'Original operator form or report action binding changed')
            original, previous, observed = [json.loads((p/f.name).read_bytes()) for p in (native,old,release)]
            if phase == 'old':
                check(original['rows']==previous['rows']==observed['rows'], 'Historical salary rows differ')
                payroll['identical_old_amount_rows'] += len(observed['rows'])
            else:
                check([r[1:] for r in original['rows']]==[r[1:] for r in observed['rows']],
                      'Newly confirmed draft salary rows differ')
            check(printed_table(previous['table_text'],phase=='new') == printed_table(observed['table_text'],phase=='new')
                  and previous['net']==observed['net']==original['net'],
                  'The printed lines, days, or net amount changed')
            file = release/(f.stem+'.pdf')
            download = pdf(release/(f.stem+'-button.pdf'))
            rendered = pdf(file)
            native_download = pdf(native/(f.stem+'-button.pdf'))
            check(sha256(file.read_bytes()).hexdigest()==actual['pdf_sha'] and download==rendered,
                  'The form button did not download the rendered payroll document')
            check(observed['linked_wage_printed'] and wage(download['text'])==wage(native_download['text']),
                  'The operator received a different linked contract wage')
            check(len(download['pixels'])==len(native_download['pixels'])==1 and download['fonts']==native_download['fonts']==FONTS
                  and download['size']==native_download['size']==[[612.0,1008.0]],
                  'Unexpected pagination, physical page size or font family')
            payroll[key] += 1
            payroll['downloads'] += 1
            payroll['contract_wages'] += 1
            payroll['one_page'] += 1
    preserve = json.loads((folder/(version+'-preservation.json')).read_bytes())
    check(preserve['tested_files']=={'old':10,'new':2} and preserve['physical_files']==2708 and preserve['unchanged_tables']==1141,
          'The print rehearsal did not preserve the private database and filestore')
    return {**payroll,'archived_originals':8,'physical_files':2708,'unchanged_tables':1141,'font_family':'Lato',
            'page_points':[612,1008]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    parser.add_argument('version')
    args = parser.parse_args()
    print(json.dumps(run(args.folder,args.version),sort_keys=True))
