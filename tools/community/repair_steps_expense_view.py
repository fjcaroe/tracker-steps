"""Deactivate Steps' uninstalled payroll-only expense form extension when the original company has no payroll."""
import fcntl
import json
import os
from pathlib import Path
import subprocess

from audit_steps_sales_schema import objects
from restore_converted_sys_cohort import check_modules, full_snapshot
from restore_native_product_backup import query
from restore_steps_expenses import ANCHORS, CHECKPOINT, INDEX, TARGET, WORK
from restore_sys_previred_pair import LOCK, require
from verify_steps_support_backup import compressed


XMLID = 'hr_payroll_expense.hr_expense_sheet_view_form_inherit_payroll'

# Removing the inactive provider's inherited view restores Odoo's original posting button and its native condition.
# The archived source view, its external ID, and its complete translated architecture remain available for reactivation.
CHANGE = """
from pathlib import Path
assert env.cr.dbname == target and {s.split(':')[0].strip() for s in Path('/proc/net/dev').read_text().splitlines()[2:]} == {'lo'}
env.cr.rollback()
view = env.ref(xmlid)
provider = env['ir.module.module'].search([('name', '=', 'hr_payroll_expense')])
assert provider and provider.state == 'uninstalled' and 'hr.payslip' not in env.registry
assert view.model == 'hr.expense.sheet' and view.id == 4509 and view.inherit_id.id == 3339 and view.mode == 'extension'
assert not env['ir.ui.view'].with_context(active_test=False).search_count([('inherit_id', '=', view.id), ('active', '=', True)])
env.cr.execute('SELECT (SELECT count(*) FROM hr_payslip), (SELECT count(*) FROM hr_contract), '
               '(SELECT count(*) FROM hr_expense_sheet WHERE payslip_id IS NOT NULL OR refund_in_payslip)')
assert env.cr.fetchone() == (0, 0, 0)
assert 'refund_in_payslip' not in env['hr.expense.sheet']._fields
assert hasattr(env['hr.expense.sheet'], 'action_sheet_move_post')
if view.active:
    view.write({'active': False})
    env.cr.commit()
print('EXPENSE_EXTENSION_ARCHIVED')
"""


def views():
    return query(TARGET, """SELECT md5(string_agg((CASE WHEN id=4509 THEN to_jsonb(v)-'active'-'write_uid'-'write_date'
        ELSE to_jsonb(v) END)::text,'' ORDER BY id)) FROM ir_ui_view v""")


def apply():
    require(Path(__file__).resolve().parent == WORK/'code' and
            json.loads((WORK/'identity.json').read_bytes())['index'] == INDEX, 'different-expense-copy')
    args = json.loads((WORK/'private-args.json').read_bytes())
    require(args[args.index('-d')+1] == TARGET and '--no-http' in args and '--net' in args, 'wrong-expense-profile')
    frozen = compressed(CHECKPOINT, 'snapshot.json.gz')
    baseline = full_snapshot(TARGET, ANCHORS)
    expected = json.loads((CHECKPOINT/'providers.json').read_bytes())
    require(check_modules(TARGET, 'hr_expense') == expected and len(expected) == 166 and
            objects(TARGET) == compressed(CHECKPOINT, 'sql-objects.json.gz'), 'changed-expense-registry')
    marker = WORK/'expense-view-migration.json'
    if marker.exists():
        before_views = json.loads(marker.read_bytes())['original_views']
    else:
        require(baseline == frozen, 'original-untouched-expense-copy-required')
        before_views = views()
        temporary = marker.with_suffix('.tmp')
        temporary.write_text(json.dumps({'original_views': before_views, 'parent': INDEX}))
        temporary.replace(marker)
    require(views() == before_views, 'different-original-views')
    command = f'target={TARGET!r}\nxmlid={XMLID!r}\n'+CHANGE
    for attempt in range(2):
        proc = subprocess.run(args, input=command.encode(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        require(proc.returncode == 0 and b'EXPENSE_EXTENSION_ARCHIVED' in proc.stdout, 'expense-view-migration-failed')
        current = full_snapshot(TARGET, ANCHORS)
        differences = [k for k, value in frozen['public_tables'].items() if value != current['public_tables'][k]]
        require(differences == ['ir_ui_view'] and views() == before_views and
                query(TARGET, 'SELECT NOT active FROM ir_ui_view WHERE id=4509') == 't' and
                all(current[k] == frozen[k] for k in frozen if k != 'public_tables') and
                objects(TARGET) == compressed(CHECKPOINT, 'sql-objects.json.gz'), 'unexpected-expense-migration-change')
        if attempt:
            require(current == first, 'second-expense-migration-changed-the-database')
        first = current
    print(json.dumps({'database': TARGET, 'parent': INDEX, 'providers': len(expected), 'archived_view': XMLID,
                      'active_form': 3339, 'unchanged_tables': len(frozen['public_tables'])-1,
                      'preserved_sequences': len(current['sequence_values']), 'repeat_identical': True}))


if __name__ == '__main__':
    os.umask(0o077)
    with open(LOCK, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        apply()
