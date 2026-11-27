"""Verify all 21 posted customer invoices and credit notes and four physical printouts against Steps."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

import pymupdf

from verify_sys_invoice_pdfs import compare_native, compare_printed_pages, verify


def compare(native_text, candidate_text, native_print, candidate_print, native_folder, candidate_folder):
    originals = native_text['documents']
    if (native_text['database'] != 'MANAGEMENT_QA_STEPS_CRM_20261126U42C' or
            candidate_text['database'] not in ('COMMUNITY_STEPS_CRM_FISCAL_20261127U45F',
                                               'COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A')):
        raise ValueError('Unexpected reference or restored database')
    for actor in (7,10):
        rows = [r for r in originals if r['actor']==actor]
        if (len({r['move'] for r in rows}) != 21 or len(rows) != 21 or
                sum(r['kind']=='out_refund' for r in rows) != 1 or
                any('error' in r or not r['reference_numbers_printed'] for r in rows)):
            raise ValueError('The original operator did not render the 21 posted documents')
    if len(originals)!=42 or originals!=candidate_text['documents']:
        raise ValueError('Original invoice text, report choice, references or permissions differ')
    for receipt, folder in ((native_print,native_folder), (candidate_print,candidate_folder)):
        if not receipt['history_unchanged']:
            raise ValueError('Printing changed original business records')
        verify(receipt,folder)
    compare_native(native_print,candidate_print)
    for key in ('renderer_sha256','text_extractor_sha256'):
        if native_print[key] != candidate_print[key]:
            raise ValueError('Physical rendering binaries differ')
    pages=compare_printed_pages(native_print,native_folder,candidate_folder)
    for page in pages:
        if page['different_pixels'] or page['different_text_colors']:
            raise ValueError('Different grayscale raster or text colors')
        filename='%s-%s.pdf' % (page['actor'],page['kind'])
        page_index=page['page']-1
        with pymupdf.open(native_folder/filename) as original, pymupdf.open(candidate_folder/filename) as candidate:
            for dpi in (96,144):
                def pixels(document):
                    bitmap=document[page_index].get_pixmap(dpi=dpi,colorspace=pymupdf.csRGB,alpha=False)
                    return bitmap.width,bitmap.height,sha256(bitmap.samples).hexdigest()
                if pixels(original)!=pixels(candidate):
                    raise ValueError('Different RGB invoice print at %d dpi' % dpi)
    return {'operators':2,'documents':21,'matching_texts':len(originals),'pdfs':len(native_print['printed']),
            'matching_pages':len(pages),'rgb_dpi':[96,144],'text_runs':sum(p['text_runs'] for p in pages),
            'drawing_paths':sum(p['drawing_paths'] for p in pages)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('native_text','candidate_text','native_print','candidate_print','native_folder','candidate_folder'):
        parser.add_argument(name,type=Path)
    args=parser.parse_args()
    observations=[json.loads(getattr(args,name).read_bytes()) for name in
                  ('native_text','candidate_text','native_print','candidate_print')]
    print(json.dumps(compare(*observations,args.native_folder,args.candidate_folder)))
