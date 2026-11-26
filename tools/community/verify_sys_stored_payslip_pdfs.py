"""Compare rendered private SyS PDFs with the stored NET on each original payslip."""

import argparse
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import unicodedata


def validate(receipt, capsule, directory):
    assert receipt['code'] == 0 and receipt['business_intact']
    report = receipt['proof']
    assert report['eight_archived_pdf_bytes_unchanged'] and len(report['slips']) == 5
    amounts = {}
    for attachment in capsule['documents']:
        amounts.setdefault(attachment['slip'], set()).add(Decimal(attachment['totals']['NET']))
    assert len(capsule['documents']) == 8 and set(amounts) == {row['slip'] for row in report['slips']}
    results = []
    for row in report['slips']:
        ident = row['slip']
        assert type(ident) is int and len(amounts[ident]) == 1 and row['printed_ids_and_amounts_verified']
        raw = (directory / f'{ident}.pdf').read_bytes()
        assert raw.startswith(b'%PDF-') and sha256(raw).hexdigest() == row['pdf_sha256']
        text = subprocess.run(['pdftotext', '-layout', '-enc', 'UTF-8', '-', '-'], input=raw, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode('utf-8')
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().upper()
        net = re.findall(r'LIQUIDO\s+A\s+RECIBIR\s*:?\s*\$\s*(-?[\d.,]+)', text)
        if len(net) != 1:
            raise ValueError('Expected one unambiguous NET summary in each generated PDF')
        assert Decimal(re.sub(r'[^\d-]', '', net[0])) in amounts[ident], 'Printed NET differs from stored NET'
        pages = len([page for page in text.split('\f') if page.strip()])
        assert pages > 0
        results.append(dict(row, pages=pages, pdf_net_matches_stored=True))
    return dict(report, slips=results, business_intact=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('receipt', 'capsule', 'pdf-dir', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    verified = validate(json.loads(args.receipt.read_bytes()), json.loads(args.capsule.read_bytes()), args.pdf_dir)
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as handle:
        json.dump(verified, handle, indent=2)
    print(f"Verified {len(verified['slips'])} regenerated payroll PDFs")
