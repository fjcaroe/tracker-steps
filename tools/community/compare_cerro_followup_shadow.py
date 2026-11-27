"""Compare posted open receivables against the native contact result for each original Cerro operator context."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import psycopg2


def compare(reference):
    raw=gzip.decompress(reference.read_bytes())
    assert hashlib.sha256(raw).hexdigest()=='3085ddbf2ce5e12e47a25d2f9f50bb3a9d3245330630bcce82e2df7626f8c711'
    native=json.loads(raw)
    assert len(native['contexts'])==64
    database='COMMUNITY_CERRO_BOM_PACKING_20261127U46D'
    options=dict(dbname=database,user='postgres',host='/dev/shm/steps-cerro-u46/socket',port=55443)
    with psycopg2.connect(**options) as con,con.cursor() as cr:
        con.set_session(readonly=True,isolation_level='REPEATABLE READ')
        cr.execute("""SELECT l.company_id,l.partner_id,sum(l.amount_residual),
                         sum(l.amount_residual) FILTER (WHERE COALESCE(l.date_maturity,l.date)<%s)
                      FROM account_move_line l JOIN account_account a ON a.id=l.account_id
                      WHERE l.parent_state='posted' AND NOT l.reconciled AND a.account_type='asset_receivable'
                          AND l.partner_id IS NOT NULL GROUP BY l.company_id,l.partner_id""",(native['date'],))
        totals={(company,partner):(float(due),float(overdue or 0)) for company,partner,due,overdue in cr.fetchall()}
        matches=0
        nonzero=0
        errors=[]
        for context,expected in native['contexts'].items():
            if expected.get('denied'):
                continue
            company=int(context.split('/')[1].split(',')[0])
            for contact in expected['values']:
                projected=totals.get((company,contact['id']),(0,0))
                if projected!=(contact['total_due'],contact['total_overdue']):
                    errors.append((context,contact['id']))
                matches+=1
                nonzero+=bool(projected[0] or projected[1])
    assert not errors, errors[:10]
    return dict(matches=matches,nonzero=nonzero,contexts=len(native['contexts']),day=native['date'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference',type=Path)
    print(json.dumps(compare(parser.parse_args().reference),sort_keys=True))
