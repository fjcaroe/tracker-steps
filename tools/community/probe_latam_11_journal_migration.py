"""Exercise the exact journal migration against the copy and a temporary truth table."""
from itertools import product

import psycopg2


def check(database, migrate):
    with psycopg2.connect(dbname=database, host="/var/run/postgresql") as conn:
        with conn.cursor() as cr:
            cr.execute("SELECT current_database(),current_user")
            assert cr.fetchone() == (database, "odoo")
            cr.execute("SELECT count(*) FROM public.account_journal WHERE type='purchase' "
                       "AND l10n_latam_use_documents AND restrict_mode_hash_table")
            eligible = cr.fetchone()[0]
            migrate(cr, "18.0.1.0")
            assert cr.rowcount == eligible
            conn.rollback()
            cr.execute("CREATE TEMP TABLE account_journal (id integer PRIMARY KEY, type text, "
                       "l10n_latam_use_documents boolean, restrict_mode_hash_table boolean) ON COMMIT DROP")
            cr.execute("SET LOCAL search_path=pg_temp,pg_catalog")
            cr.execute("SELECT 'account_journal'::regclass='pg_temp.account_journal'::regclass, "
                       "'account_journal'::regclass<>'public.account_journal'::regclass")
            assert cr.fetchone() == (True, True)
            cases = list(product(("purchase", "sale"), (True, False, None), (True, False, None)))
            for pk, row in enumerate(cases):
                cr.execute("INSERT INTO account_journal VALUES (%s,%s,%s,%s)", (pk, *row))
            migrate(cr, "18.0.1.0")
            assert cr.rowcount == 1
            cr.execute("SELECT restrict_mode_hash_table FROM account_journal ORDER BY id")
            after = [row[0] for row in cr.fetchall()]
            assert after == [False if typ == "purchase" and docs and locked else locked for typ, docs, locked in cases]
            conn.rollback()
    return {"eligible_in_original": eligible, "synthetic": len(cases), "synthetic_changed": 1, "rolled_back": True}
