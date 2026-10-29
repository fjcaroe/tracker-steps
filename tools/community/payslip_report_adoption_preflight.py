"""Inspect report action identity without rendering or copying Enterprise QWeb.

This is a read-only admission plan, never an importer. An alias to another
numeric action does not preserve original report 462 or its structure FKs.
"""
import argparse
import json
import os
from pathlib import Path
import re


ORIGINAL_ID = 462
LEGACY = ('hr_payroll', 'action_report_payslip')
COMMUNITY_RENDERER = 'step_simpledigital_oca_base.report_payslip'


def assess(contract):
    original = next((row for row in contract['actions'] if row['id'] == ORIGINAL_ID), None)
    alias = next((row for row in contract['xmlids'] if (row['module'], row['name']) == LEGACY), None)
    report = next((row for row in contract['reports'] if row['id'] == ORIGINAL_ID), None)
    blockers = []
    if original and (not report or report['model'] != 'hr.payslip' or report['report_type'] != 'qweb-pdf'):
        blockers.append('ORIGINAL_ACTION_ID_COLLISION')
    if alias and (alias['model'] != 'ir.actions.report' or alias['res_id'] != ORIGINAL_ID):
        blockers.append('LEGACY_ALIAS_DOES_NOT_PRESERVE_NUMERIC_ID')
    if report and report['report_name'] != COMMUNITY_RENDERER:
        blockers.append('ORIGINAL_ACTION_NOT_ADOPTED_TO_REAL_COMMUNITY_RENDERER')
    if COMMUNITY_RENDERER not in contract['template_keys']:
        blockers.append('COMMUNITY_TEMPLATE_MISSING')
    return {'original_action_id': ORIGINAL_ID, 'numeric_id_available': original is None,
        'existing_original_report_identity': bool(report and not {'ORIGINAL_ACTION_ID_COLLISION',
            'LEGACY_ALIAS_DOES_NOT_PRESERVE_NUMERIC_ID'} & set(blockers)),
        'preflight_only': True, 'conversion_ready': False, 'dependencies_may_change': False,
        'functional_pdf_certified': False, 'blockers': blockers,
        'required_plan': ['Preserve unrelated target actions; never overwrite a numeric collision',
            'Reserve original action ID and XML ID row identities only in the admitted cold target space',
            'Bind the same original action to an existing tested Community renderer explicitly',
            'Preserve structure report_id FKs, model binding, roles, names and translations',
            'Prove real authorized PDF output and closed-history preservation before conversion']}


def inspect(cursor):
    cursor.execute('SHOW transaction_read_only')
    if cursor.fetchone()[0] != 'on':
        raise ValueError('Report inspection requires a read-only transaction')
    cursor.execute("SELECT id,module,name,model,res_id,noupdate FROM ir_model_data WHERE "
        "(module IN ('hr_payroll','payroll') AND name='action_report_payslip') OR "
        "(model='ir.actions.report' AND res_id=462) ORDER BY id")
    aliases = [dict(zip(('id', 'module', 'name', 'model', 'res_id', 'noupdate'), row)) for row in cursor.fetchall()]
    ids = sorted({ORIGINAL_ID} | {row['res_id'] for row in aliases if row['model'] == 'ir.actions.report'})
    cursor.execute('SELECT id,name,type,binding_model_id,binding_type,binding_view_types FROM ir_actions WHERE id=ANY(%s) ORDER BY id', [ids])
    actions = [dict(zip(('id', 'name', 'type', 'binding_model_id', 'binding_type', 'binding_view_types'), row)) for row in cursor.fetchall()]
    cursor.execute('SELECT id,name,model,report_type,report_name,report_file,attachment_use,print_report_name,paperformat_id '
                   'FROM ir_act_report_xml WHERE id=ANY(%s) ORDER BY id', [ids])
    reports = [dict(zip(('id', 'name', 'model', 'report_type', 'report_name', 'report_file',
        'attachment_use', 'print_report_name', 'paperformat_id'), row)) for row in cursor.fetchall()]
    cursor.execute('SELECT uid,gid FROM res_groups_report_rel WHERE uid=ANY(%s) ORDER BY uid,gid', [ids])
    groups = [dict(zip(('action_id', 'group_id'), row)) for row in cursor.fetchall()]
    cursor.execute("SELECT key FROM ir_ui_view WHERE type='qweb' AND key=ANY(%s) ORDER BY key",
        [[COMMUNITY_RENDERER, 'hr_payroll.report_payslip_lang']])
    templates = [row[0] for row in cursor.fetchall()]
    cursor.execute("SELECT model,name,ttype,store,related,company_dependent FROM ir_model_fields "
        "WHERE model IN ('hr.payslip','hr.payroll.structure') AND name='journal_id' ORDER BY model")
    journal = [dict(zip(('model', 'name', 'type', 'stored', 'related', 'company_dependent'), row)) for row in cursor.fetchall()]
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
                   "AND table_name='hr_payroll_structure' AND column_name='report_id'")
    links = None
    if cursor.fetchone():
        cursor.execute('SELECT id,report_id FROM hr_payroll_structure ORDER BY id')
        links = [dict(zip(('structure_id', 'report_id'), row)) for row in cursor.fetchall()]
    result = {'database': cursor.connection.info.dbname, 'read_only': True, 'orm_loaded': False,
        'payroll_rules_evaluated': False, 'historical_payroll_read': False,
        'enterprise_qweb_bodies_exported': False, 'actions': actions, 'reports': reports,
        'xmlids': aliases, 'groups': groups, 'template_keys': templates,
        'structure_report_references': links, 'journal_field_contract': journal}
    result['assessment'] = assess(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or not re.fullmatch(r'(?:COMMUNITY_[A-Za-z0-9_]+|MANAGEMENT_QA_(?:CERRO|SYS)_[A-Za-z0-9_]+)', args.database):
        raise ValueError('Run as root against an existing private reference only')
    if not args.output.resolve().is_relative_to(Path('/opt/steps-validation')) or args.output.exists():
        raise ValueError('Use a new private output artifact')
    from validate_payroll_relation_storage import connect
    with connect(args.database) as connection:
        connection.set_session(readonly=True, isolation_level='REPEATABLE READ')
        with connection.cursor() as cursor:
            result = inspect(cursor)
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, default=str)
    print('PAYSLIP_REPORT_PREFLIGHT', args.database, result['assessment']['blockers'])


if __name__ == '__main__':
    main()
