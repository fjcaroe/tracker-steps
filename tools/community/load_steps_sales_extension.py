"""Install the selected extension while retaining the required columns from the private sales backup."""
import hashlib
import inspect
import json
from pathlib import Path
import sys

from preflight_original_history_storage import require


PROFILES = {
    'COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H': 'step_helpdesk_tickets',
    'COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H2': 'step_helpdesk_tickets',
    'COMMUNITY_SYS_FISCAL_PRINT_20261127U45P': 'step_report_print_colors',
    'COMMUNITY_STEPS_CRM_DOC_20261127U43X': 'step_document_library,step_document_library_portal',
    'COMMUNITY_STEPS_CRM_DOC_20261127U44P': 'step_document_library,step_document_library_portal,step_report_print_colors',
    'COMMUNITY_STEPS_CRM_PRINT_20261127U43Y': 'step_report_print_colors',
}
SQL_SHA = '0470f3e4cfa2736ca1b402bad8e5047edb39fc79d68de2ae6f81853318722bff'


def guarded_command(command, work, frozen):
    executable, = [i for i, arg in enumerate(command) if arg.endswith('/odoo-bin')]
    columns = {name: value[0] for name, value in frozen['columns'].items() if value[1]}
    plan = work/'code/required-columns.json'
    payload = json.dumps(columns, sort_keys=True).encode()
    if not plan.exists():
        with plan.open('xb') as handle:
            handle.write(payload)
        plan.chmod(0o644)
    require(plan.read_bytes() == payload and columns, 'required-sales-columns-differ')
    return [*command[:executable], str(work/'code/load_steps_sales_extension.py'), command[executable],
            str(plan), hashlib.sha256(payload).hexdigest(), *command[executable+1:]]


def main():
    binary, plan, checksum, *args = sys.argv[1:]
    db = args[args.index('-d')+1]
    switches = [arg for arg in args if arg in ('-i','-u')]
    require(db in PROFILES and '--db-filter=^'+db+'$' in args and '--no-http' in args
            and '--stop-after-init' in args and '--max-cron-threads=0' in args
            and (switches==['-i'] or (switches==['-u'] and db=='COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H2'))
            and args[args.index(switches[0])+1] == PROFILES[db], 'private-install-required')
    payload = Path(plan).read_bytes()
    require(hashlib.sha256(payload).hexdigest() == checksum, 'required-columns-plan-changed')
    columns = json.loads(payload)
    runtime = Path(binary).resolve(strict=True).parent
    sys.path.insert(0, str(runtime))
    from odoo import cli
    from odoo.tools import sql
    original = sql.drop_not_null
    handler = runtime/'odoo/tools/sql.py'
    require(Path(inspect.getsourcefile(original)).resolve() == handler
            and hashlib.sha256(handler.read_bytes()).hexdigest() == SQL_SHA, 'unreviewed-odoo-required-handler')
    preserved = set()

    def guard(cr, table, column):
        require(cr.dbname == db, 'wrong-database-for-field-update')
        key = table + '.' + column
        if key not in columns:
            return original(cr, table, column)
        cr.execute("""SELECT format_type(a.atttypid,a.atttypmod),a.attnotnull FROM pg_attribute a
            JOIN pg_class c ON c.oid=a.attrelid WHERE c.relnamespace='public'::regnamespace
            AND c.relname=%s AND a.attname=%s AND NOT a.attisdropped""", (table, column))
        require(cr.fetchall() == [(columns[key], True)], 'original-required-column-changed-'+key)
        preserved.add(key)

    sql.drop_not_null = guard
    try:
        sys.argv = [binary, *args]
        cli.main()
    finally:
        sql.drop_not_null = original
        print('STEPS_REQUIRED_COLUMNS '+json.dumps(sorted(preserved)), flush=True)


if __name__ == '__main__':
    main()
