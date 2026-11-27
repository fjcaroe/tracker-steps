"""Recheck the sealed Steps sales, filing, accounting and invoice evidence together before a cold recovery."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

import pymupdf

from verify_steps_accounting_history import compare as compare_accounting
from verify_steps_payment_cycle import verify as verify_payment_cycle
from verify_steps_fiscal_reports import compare as compare_fiscal_reports
from verify_steps_sale_documents import verify as compare_sale_documents


def verify(folder, run_prefix='U46A', payments=False, fiscal_print_run=None):
    fiscal_print_run = fiscal_print_run or run_prefix+'Fiscal'
    if not run_prefix.isalnum() or not fiscal_print_run.isalnum():
        raise ValueError('Invalid evidence run identifier')
    evidence = {}
    candidate = 'fiscal' if payments else 'integrated'
    def receipt(stem, exact=False):
        if not exact and stem.startswith('U46A') and not stem.startswith('U46A-steps-fiscal-integration-'):
            stem=run_prefix+stem[4:]
            if payments and stem.endswith('-integrated'):
                stem=stem.removesuffix('-integrated')+'-fiscal'
        path = folder/(stem+'.json')
        raw = path.read_bytes()
        evidence[path.name]=sha256(raw).hexdigest()
        return json.loads(raw)

    admission='U46F-steps-all-166-' if payments else 'U46A-steps-fiscal-integration-'
    install=receipt(admission+'install')
    repeat=receipt(admission+'repeat')
    if (not repeat['repeat'] or install['repeat'] or install['modules']!=(166 if payments else 165) or
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
        receipt('U45PFB-steps-invoice-pdfs-native'),receipt(fiscal_print_run+'-steps-invoice-pdfs-'+candidate, exact=True),
        folder/'U45PFB-steps-fiscal-pages-native',folder/(fiscal_print_run+'-steps-fiscal-pages-'+candidate))
    native_sales=receipt('U43SG-steps-sale-reports-native')
    integrated_sales=receipt('U46ASale-steps-sale-reports-integrated')
    sales = compare_sale_documents(native_sales,integrated_sales,receipt('U43SI-steps-sale-reports-native'),
                                   receipt('U46AOrder-steps-sale-reports-integrated'))
    for original,current in zip(native_sales['documents'],integrated_sales['documents']):
        for dpi in (96,144):
            printed = []
            for name,row in (('native',original),(candidate,current)):
                path=folder/(run_prefix+'Sale-sale-print-comparison')/name/('7-%d.pdf' % row['id'])
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
    proof={'database':combined_account['database'],'providers':install['modules'],
            'accounting':financial,'printed_invoices':fiscal,'sales':sales,'sales_rgb_dpi':[96,144],
            'library_elements':scopes['documents'],'library_permission_decisions':scopes['permission_decisions'],
            'historical_link_calls':portal['files']*len(portal['scopes']),'receipts':evidence}

    if payments:
        proof['packages']={key:value for key,value in install.items() if key.endswith('_package')}
        proof['payment_cycle']=verify_payment_cycle(receipt('U46PayMenu-steps-payment-history-native'),
            receipt(run_prefix+'Payment-steps-payment-history-fiscal'),receipt('U46PayEnd-steps-manual-payment-native'),
            receipt(run_prefix+'Payment-steps-manual-payment-fiscal'))
    else:
        proof['package']=install['package']
    return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    parser.add_argument('--run-prefix',default='U46A')
    parser.add_argument('--payments',action='store_true')
    parser.add_argument('--fiscal-print-run',help='Run that retained the four physical invoice PDFs')
    args=parser.parse_args()
    print(json.dumps(verify(args.folder,args.run_prefix,args.payments,args.fiscal_print_run),sort_keys=True))
