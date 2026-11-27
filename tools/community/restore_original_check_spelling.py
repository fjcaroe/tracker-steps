"""Recover original PostgreSQL CHECK definitions when pg_restore distributes an array cast over its literals."""
import argparse
import gzip
import json
import re
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql


CHECKS = {
    ("account_move_line", "account_move_line_check_accountable_required_fields"),
    ("account_move_line", "account_move_line_check_amount_currency_balance_sign"),
    ("account_move_line", "account_move_line_check_credit_debit"),
    ("account_move_line", "account_move_line_check_non_accountable_fields_null"),
    ("calendar_recurrence", "calendar_recurrence_month_day"),
    ("hr_expense_sheet", "hr_expense_sheet_journal_id_required_posted"),
    ("hr_leave_accrual_level", "hr_leave_accrual_level_check_dates"),
    ("mail_notification", "mail_notification_notification_partner_required"),
}
LITERAL = r"'[-a-zA-Z0-9_ ]+'::character varying"
LITERALS = rf"(?P<values>{LITERAL}(?:, {LITERAL})+)"
ARRAY_CAST = re.compile(r"\(ARRAY\[" + LITERALS + r"\]\)::text\[\]")
LIST_OPERATOR = re.compile(r"\((?P<column>[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)\)::text (?P<op>= ANY|<> ALL) \("
                           + ARRAY_CAST.pattern + r"\)")


def clauses(source):
    def distributed(match):
        return "ARRAY[" + ", ".join("(" + v + ")::text" for v in match["values"].split(", ")) + "]"

    def membership(match):
        values = ", ".join(v.split("::", 1)[0] for v in match["values"].split(", "))
        operator = "IN" if match["op"] == "= ANY" else "NOT IN"
        return f"{match['column']} {operator} ({values})"

    expanded, arrays = ARRAY_CAST.subn(distributed, source)
    original_form, conditions = LIST_OPERATOR.subn(membership, source)
    if not arrays or arrays != conditions:
        raise ValueError("Unsupported source CHECK expression")
    return expanded, original_form


def restore_spelling(target, snapshot):
    if not re.fullmatch(r"COMMUNITY_CERRO_PAYROLL_RECOVERY_[A-Z0-9_]{1,25}", target):
        raise ValueError("Cerro private recovery target required")
    archive = snapshot if isinstance(snapshot, bytes) else Path(snapshot).read_bytes()
    expected = json.loads(gzip.decompress(archive))["constraints"]
    with psycopg2.connect(dbname=target) as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL search_path=pg_catalog,public")
            cur.execute("""
                SELECT t.relname,c.conname,pg_get_constraintdef(c.oid),c.convalidated,
                       c.contype,c.conislocal,c.coninhcount,obj_description(c.oid,'pg_constraint')
                  FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
                  JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public'
            """)
            rows = {(table, name): (body, valid, kind, local, inherited, comment)
                    for table, name, body, valid, kind, local, inherited, comment in cur.fetchall()}
            if {".".join(k) for k in rows} != expected.keys():
                raise ValueError("Constraint identities differ from the frozen database")
            changes = []
            for (table, name), (actual, valid, kind, local, inherited, comment) in sorted(rows.items()):
                body, original_valid = expected[table + "." + name]
                if [actual, valid] == [body, original_valid]:
                    continue
                if (table, name) not in CHECKS or not (original_valid and valid and local and not inherited and kind == "c"):
                    raise ValueError("An unexpected constraint differs from the frozen catalog")
                expanded, original_form = clauses(body)
                if expanded != actual:
                    raise ValueError("The SQL difference extends beyond the expected element casts")
                probe = "cerro_original_check_" + str(len(changes))
                cur.execute(sql.SQL("CREATE TEMP TABLE {} (LIKE {}) ON COMMIT DROP").format(
                    sql.Identifier(probe), sql.Identifier("public", table)))
                cur.execute(sql.SQL("ALTER TABLE {} ADD CONSTRAINT probe {}").format(
                    sql.Identifier("pg_temp", probe), sql.SQL(original_form)))
                cur.execute("""
                    SELECT pg_get_constraintdef(oid),convalidated FROM pg_constraint
                     WHERE conrelid=to_regclass(%s) AND conname='probe'
                """, ["pg_temp." + probe])
                if list(cur.fetchone()) != [body, True]:
                    raise ValueError("PostgreSQL did not reproduce the exact native definition in the temporary table")
                changes.append((table, name, original_form, body, comment))
            for table, name, form, body, comment in changes:
                relation, identifier = sql.Identifier("public", table), sql.Identifier(name)
                cur.execute(sql.SQL("ALTER TABLE {} DROP CONSTRAINT {}, ADD CONSTRAINT {} {}").format(
                    relation, identifier, identifier, sql.SQL(form)))
                if comment is not None:
                    cur.execute(sql.SQL("COMMENT ON CONSTRAINT {} ON {} IS {}").format(identifier, relation, sql.Literal(comment)))
                cur.execute("""
                    SELECT pg_get_constraintdef(oid),convalidated,obj_description(oid,'pg_constraint')
                      FROM pg_constraint WHERE conrelid=to_regclass(%s) AND conname=%s
                """, ["public." + table, name])
                if cur.fetchone() != (body, True, comment):
                    raise ValueError("The final checked definition or comment differs")
        return {table + "." + name: form for table, name, form, body, comment in changes}


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("target")
    cli.add_argument("snapshot")
    args = cli.parse_args()
    snapshot = sys.stdin.buffer.read() if args.snapshot == "-" else args.snapshot
    print(json.dumps(restore_spelling(args.target, snapshot)))
