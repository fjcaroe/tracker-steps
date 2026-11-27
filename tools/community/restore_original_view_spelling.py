"""Recreate the original six Cerro views whose varchar array casts change on pg_restore."""
import json
import sys

import psycopg2
from psycopg2 import sql

from converted_cohort_profile import converted_profile
from restore_original_check_spelling import clauses


VIEWS = ("hr_contract_history", "hr_leave_employee_type_report", "hr_leave_report_calendar",
         "purchase_bill_union", "report_project_task_user", "report_stock_quantity")


def view_catalog(cursor):
    cursor.execute("""
        SELECT c.relname,pg_get_viewdef(c.oid,false),pg_get_userbyid(c.relowner),c.relacl::text,
               c.reloptions,obj_description(c.oid,'pg_class')
          FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
         WHERE n.nspname='public' AND c.relkind='v' AND c.relname=ANY(%s)
    """, [list(VIEWS)])
    rows = {name: (body, owner, acl, options, comment) for name, body, owner, acl, options, comment in cursor.fetchall()}
    if set(rows) != set(VIEWS):
        raise ValueError("Incomplete original view inventory")
    return rows


def restore_views(source, target):
    if converted_profile(source, target) != "cerro":
        raise ValueError("A private Cerro conversion and recovery pair is required")
    with psycopg2.connect(dbname=source) as database, psycopg2.connect(dbname=target) as clone:
        database.set_session(readonly=True, isolation_level="REPEATABLE READ")
        with database.cursor() as original, clone.cursor() as restored:
            original.execute("SET LOCAL search_path=pg_catalog,public")
            restored.execute("SET LOCAL search_path=pg_catalog,public")
            baseline = view_catalog(original)
            current = view_catalog(restored)
            work = {}
            for name in VIEWS:
                body, *metadata = baseline[name]
                existing, *target_meta = current[name]
                if target_meta != metadata:
                    raise ValueError("Unexpected view ownership, permissions, options or comment")
                if body == existing:
                    continue
                expanded, form = clauses(body)
                if expanded != existing:
                    raise ValueError("Restored view differs beyond its expected array casts")
                probe = "cerro_original_view_" + str(len(work))
                restored.execute(sql.SQL("CREATE TEMP VIEW {} AS {}").format(sql.Identifier(probe), sql.SQL(form)))
                restored.execute("SELECT pg_get_viewdef(to_regclass(%s),false)", ["pg_temp." + probe])
                if restored.fetchone() != (body,):
                    raise ValueError("The temporary view does not have the original definition")
                work[name] = form
            for name, form in work.items():
                restored.execute(sql.SQL("CREATE OR REPLACE VIEW {} AS {}").format(sql.Identifier("public", name), sql.SQL(form)))
            if view_catalog(restored) != baseline:
                raise ValueError("Original view definitions and policies differ after replay")
    return work


if __name__ == "__main__":
    print(json.dumps(restore_views(sys.argv[1], sys.argv[2])))
