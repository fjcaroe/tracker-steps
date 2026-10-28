"""Compare a preserved SyS PDF with its linked SQL capsule; no report generation.

The result contains a private printed wage. A document observation does not
certify the master timeline, all salary rules, or the financial/legal result.
Only the observed one-page Simple Digital English/Spanish template is supported.
"""
import argparse
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from pypdf import PdfReader


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capsule',type=Path,required=True)
    p.add_argument('--document',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    private=Path.home()/'.codex/local-artifacts'
    assert all(path.resolve().is_relative_to(private) or str(path.resolve()).startswith('/opt/steps-validation/')
               for path in (a.capsule,a.document,a.output))
    capsule=json.loads(a.capsule.read_text());proof=json.loads((a.document.parent/'document-proof.json').read_text())
    assert proof['read_only'] and not proof['report_generated']
    assert proof['capsule_sha256']==hashlib.sha256(a.capsule.read_bytes()).hexdigest()
    raw=a.document.read_bytes();assert hashlib.sha256(raw).hexdigest()==proof['pdf_sha256']
    assert hashlib.sha1(raw).hexdigest()==proof['attachment']['checksum']
    reader=PdfReader(a.document);assert len(reader.pages)==1,'Unreviewed template/page layout'
    text=unicodedata.normalize('NFKD',reader.pages[0].extract_text(extraction_mode='layout')).encode('ascii','ignore').decode().upper()
    def one(pattern):
        matches=re.findall(pattern,text)
        assert len(matches)==1,'Missing or ambiguous reference label'
        return matches[0]
    def money(label):
        value=one(label+r'\s*\$\s*([0-9.]+)')
        assert re.fullmatch(r'(?:[1-9]\d{0,2}(?:\.\d{3})+|0|[1-9]\d*)',value),'Unsupported CLP display'
        return Decimal(value.replace('.',''))
    wage=money(r'CONTRACT WAGE \(MONTHLY\):')
    basic=money('SUELDO BASE');taxable=money('SUELDO IMPONIBLE')
    earnings=money('TOTAL HABERES');net=money('LIQUIDO A RECIBIR')
    start,end=one(r'PAY PERIOD:\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})')
    selected=capsule['selected_case'];totals=selected['stored_totals']
    assert datetime.strptime(start,'%d/%m/%Y').date().isoformat()==selected['date_from']
    assert datetime.strptime(end,'%d/%m/%Y').date().isoformat()==selected['date_to']
    result={'read_only':True,'report_generated':False,'payroll_computed':False,'financial_certified':False,
        'master_timeline_certified':False,'documentary_wage_observed':True,'private_payroll_amounts_exported':True,
        'direct_employee_identifiers_exported':False,'formula_bodies_exported':False,
        'pdf_sha256':proof['pdf_sha256'],'capsule_sha256':proof['capsule_sha256'],
        'comparator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'printed_contract_wage':str(wage),'selected_period':selected['date_to'][:7],
        'basic_matches_stored':basic==Decimal(totals['BASIC']),
        'net_matches_stored':net==Decimal(totals['NET']),
        'taxable_matches_stored_gross':taxable==Decimal(totals['GROSS']),
        'total_earnings_matches_stored_gross':earnings==Decimal(totals['GROSS']),
        'printed_wage_matches_basic':wage==basic,
        'printed_wage_is_current_contract_wage':wage==Decimal(selected['basis']['current_contract_wage'])}
    a.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key.endswith('matches_stored') or key in
        ('documentary_wage_observed','financial_certified','taxable_matches_stored_gross','total_earnings_matches_stored_gross')}))


if __name__=='__main__':main()
