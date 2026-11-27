"""Recheck the sealed Steps sales, filing, accounting and invoice evidence together before a cold recovery."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

import pymupdf

from verify_steps_accounting_history import compare as compare_accounting
from verify_steps_fiscal_reports import compare as compare_fiscal_reports
from verify_steps_sale_documents import verify as compare_sale_documents


def verify(folder):
    evidence = {}
    def receipt(stem):
        path = folder/(stem+'.json')
        raw = path.read_bytes()
        evidence[path.name]=sha256(raw).hexdigest()
        return json.loads(raw)

    install=receipt('U46A-steps-fiscal-integration-install')
    repeat=receipt('U46A-steps-fiscal-integration-repeat')
    if (not repeat['repeat'] or install['repeat'] or install['modules']!=165 or
            {k:v for k,v in repeat.items() if k!='repeat'} != {k:v for k,v in install.items() if k!='repeat'}):
        raise ValueError('Different integrated module installation and update')
    native_account = receipt('U45D3-steps-accounting-native')
    combined_account = receipt('U46AAccount-steps-accounting-integrated')
    financial = compare_accounting(native_account,combined_account)
    if any(financial['missing_model_fields'].values()) or any(
        any(c[k] != n[k] for k in ('archived_files','document_actions'))
        for c,n in zip(combined_account['cases'],native_account['cases'])
    ):
        raise ValueError('Missing original accounting or linked-file permissions')
    fiscal = compare_fiscal_reports(receipt('U45IR-steps-invoice-text-native'),receipt('U46AFiscal-steps-invoice-text-integrated'),
        receipt('U45PFB-steps-invoice-pdfs-native'),receipt('U46AFiscal-steps-invoice-pdfs-integrated'),
        folder/'U45PFB-steps-fiscal-pages-native',folder/'U46AFiscal-steps-fiscal-pages-integrated')
    native_sales=receipt('U43SG-steps-sale-reports-native')
    integrated_sales=receipt('U46ASale-steps-sale-reports-integrated')
    sales = compare_sale_documents(native_sales,integrated_sales,receipt('U43SI-steps-sale-reports-native'),
                                   receipt('U46AOrder-steps-sale-reports-integrated'))
    for original,current in zip(native_sales['documents'],integrated_sales['documents']):
        for dpi in (96,144):
            printed = []
            for name,row in (('native',original),('integrated',current)):
                path=folder/'U46ASale-sale-print-comparison'/name/('7-%d.pdf' % row['id'])
                if sha256(path.read_bytes()).hexdigest()!=row['bytes_sha256']:
                    raise ValueError('The retained sales PDF differs from the report action')
                with pymupdf.open(path) as pdf:
                    rendered=[]
                    for page in pdf:
                        pixels=page.get_pixmap(dpi=dpi,colorspace=pymupdf.csRGB,alpha=False)
                        rendered.append((pixels.width,pixels.height,sha256(pixels.samples).hexdigest()))
                    printed.append(rendered)
            if printed[0]!=printed[1]:
                raise ValueError('The sales printout differs in RGB at %d dpi' % dpi)
    scopes=receipt('U46ADocs-integrated-sales-documents-integrated')
    staff=receipt('U46ADocs-steps-library-reads-integrated')
    portal=receipt('U46ADocsPortal-steps-library-reads-integrated')
    if (scopes!=receipt('U44H3-integrated-sales-documents-combined') or scopes['permission_decisions']!=686
            or staff!=receipt('U44DA-steps-library-reads-native') or portal!=receipt('U44PX-steps-library-reads-native')):
        raise ValueError('Customer opportunities or original file access changed')
    return {'database':combined_account['database'],'providers':install['modules'],'package':install['package'],
            'accounting':financial,'printed_invoices':fiscal,'sales':sales,'sales_rgb_dpi':[96,144],
            'library_elements':scopes['documents'],'library_permission_decisions':scopes['permission_decisions'],
            'historical_link_calls':portal['files']*len(portal['scopes']),'receipts':evidence}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    args=parser.parse_args()
    print(json.dumps(verify(args.folder),sort_keys=True))
