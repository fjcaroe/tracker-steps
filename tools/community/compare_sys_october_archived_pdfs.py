"""Compare every archived October PDF in the private SyS cohort with its own stored lines."""

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import unicodedata


def capture(shell_env, company, uid):
    """Return a private comparison capsule from a read-only Odoo shell."""
    from odoo import api

    assert re.fullmatch(r'(?:MANAGEMENT_QA_SYS_PREVIRED_|COMMUNITY_SYS_PREVIRED_)[A-Z0-9_]+', shell_env.cr.dbname)
    with shell_env.registry.cursor() as cr:
        cr.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        env = api.Environment(cr, uid, {'allowed_company_ids': [company]})
        assert not env.su and env.company.id == company and env.company in env.user.company_ids
        cr.execute("""SELECT id FROM hr_payslip WHERE company_id=%s AND date_from='2026-10-01'
                      AND date_to='2026-10-31' AND state IN ('done','paid') ORDER BY id""", [company])
        slips = env['hr.payslip'].browse([r[0] for r in cr.fetchall()])
        slips.check_access('read')
        assert len(slips) == 5
        result = []
        for slip in slips:
            cr.execute("""SELECT id,code,total::text FROM hr_payslip_line WHERE slip_id=%s
                          AND code IN ('BASIC','GROSS','NET') ORDER BY id""", [slip.id])
            lines = cr.fetchall()
            assert Counter(r[1] for r in lines) == {'BASIC': 1, 'GROSS': 1, 'NET': 1}
            records = env['hr.payslip.line'].browse([r[0] for r in lines])
            records.check_access('read')
            records.check_field_access_rights('read', ['code', 'total'])
            cr.execute("""SELECT id FROM ir_attachment WHERE res_model='hr.payslip' AND res_id=%s
                          AND mimetype='application/pdf' ORDER BY id""", [slip.id])
            docs = env['ir.attachment'].browse([r[0] for r in cr.fetchall()])
            docs.check_access('read')
            assert docs
            for doc in docs:
                raw = doc.raw
                assert raw.startswith(b'%PDF-') and len(raw) == doc.file_size
                assert hashlib.sha1(raw).hexdigest() == doc.checksum
                assert doc.store_fname == doc.checksum[:2] + '/' + doc.checksum
                result.append({'slip': slip.id, 'attachment': doc.id, 'object': doc.store_fname,
                               'pdf_sha256': hashlib.sha256(raw).hexdigest(),
                               'totals': {code: value for _, code, value in lines}})
        return {'period': '2026-10', 'company': company, 'uid': uid, 'documents': result}


def printed_amount(text, label):
    values = re.findall(r'\b' + label + r'\s*:?\s*\$\s*(-?(?:[0-9]{1,3}(?:\.[0-9]{3})+|[0-9]+))(?![.,\d])', text)
    if len(values) == 1:
        return Decimal(values[0].replace('.', ''))
    return None


def compare(capsule, archive):
    assert capsule['period'] == '2026-10' and len({r['slip'] for r in capsule['documents']}) == 5
    result = []
    with tarfile.open(archive, 'r:') as stream:
        for row in capsule['documents']:
            member = stream.getmember(row['object'])
            assert member.isfile() and 0 < member.size < 10_000_000
            with stream.extractfile(member) as src:
                raw = src.read()
            assert hashlib.sha256(raw).hexdigest() == row['pdf_sha256']
            text = subprocess.run(['pdftotext','-layout','-enc','UTF-8','-','-'], input=raw,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout.decode()
            text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().upper()
            current = {}
            for code, label in [('BASIC', 'SUELDO BASE'), ('GROSS', 'SUELDO IMPONIBLE'), ('NET', 'LIQUIDO A RECIBIR')]:
                value = printed_amount(text, label)
                current[code] = None if value is None else value == Decimal(row['totals'][code])
            result.append({'slip': row['slip'], 'attachment': row['attachment'],
                           'pdf_sha256': row['pdf_sha256'], 'matches_stored': current})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('capsule', 'archive', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    for path in (args.capsule, args.archive, args.output):
        assert (path.resolve().is_relative_to(Path.home() / '.codex/local-artifacts')
                or path.resolve().is_relative_to(Path('/opt/steps-validation').resolve()))
    rows = compare(json.loads(args.capsule.read_bytes()), args.archive)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(rows, out, indent=2)
    print('Archived PDFs:', len(rows))
    for key in ('BASIC', 'GROSS', 'NET'):
        print(key, dict(Counter(r['matches_stored'][key] for r in rows)))


if __name__ == '__main__':
    main()
