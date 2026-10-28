"""Read the user-approved SyS reference without ORM reads or payroll computation.

All output is private. No employee names/IDs/RUTs or formula bodies are exported.
The capsule is evidence for future replay, not certification or identity adoption.
"""
import argparse
import ast
import configparser
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert str(args.output.resolve()).startswith('/opt/steps-validation/')
    cfg = configparser.ConfigParser(interpolation=None)
    assert cfg.read('/etc/odoo18-sys.conf') and cfg['options']['db_name'] == 'SyS'

    def query(statement):
        assert statement.startswith(('SELECT ', 'SHOW '))
        return subprocess.check_output([
            'sudo', '-u', 'postgres', 'env', 'PGOPTIONS=-c default_transaction_read_only=on',
            'psql', '-XAt', '-v', 'ON_ERROR_STOP=1', '-d', 'SyS', '-c', statement], text=True).strip()

    assert query('SHOW default_transaction_read_only') == 'on'
    provider = next(Path(p.strip()) / 'l10n_cl_simpledigital_payroll'
                    for p in cfg['options']['addons_path'].split(',')
                    if (Path(p.strip()) / 'l10n_cl_simpledigital_payroll/__manifest__.py').is_file())
    manifest = ast.literal_eval((provider / '__manifest__.py').read_text(encoding='utf-8-sig'))
    assert manifest['license'] in ('AGPL-3', 'LGPL-3')
    source = json.loads(query("SELECT jsonb_build_object("
        "'slips',(SELECT coalesce(jsonb_agg(jsonb_build_object('id',id,'state',state,'date_from',date_from,'date_to',date_to,'structure_id',struct_id) ORDER BY id),'[]') FROM hr_payslip WHERE state IN ('done','paid')),"
        "'lines',(SELECT coalesce(jsonb_agg(jsonb_build_object('id',l.id,'slip_id',l.slip_id,'code',l.code,'salary_rule_id',l.salary_rule_id,'total',l.total::text,'write_date',l.write_date) ORDER BY l.id),'[]') FROM hr_payslip_line l JOIN hr_payslip s ON s.id=l.slip_id WHERE s.state IN ('done','paid') AND l.code IN ('BASIC','GROSS','NET')))") )
    indexed = {row['id']: dict(row, concepts={}) for row in source['slips']}
    for line in source['lines']:
        indexed[line['slip_id']]['concepts'].setdefault(line['code'], []).append(line)
    ambiguous = []
    incomplete = []
    complete = []
    for slip in indexed.values():
        if set(slip['concepts']) != {'BASIC', 'GROSS', 'NET'}:
            incomplete.append(slip['id'])
        uncertain = False
        for code, rows in slip['concepts'].items():
            identities = {row['salary_rule_id'] for row in rows}
            if None in identities or len(identities) > 1:
                uncertain = True
                ambiguous.append({'slip_id': slip['id'], 'code': code,
                                  'rule_ids': sorted(identities, key=lambda value: value or 0),
                                  'line_ids': [row['id'] for row in rows]})
        if not uncertain and slip['id'] not in incomplete:
            slip['stored_totals'] = {code: str(sum((Decimal(row['total']) for row in rows), Decimal(0)))
                                     for code, rows in slip['concepts'].items()}
            complete.append(slip)
    # Prefer a completed previous month, never assume current contract data historical.
    candidates = [row for row in complete if row['date_to'] < date.today().replace(day=1).isoformat()]
    selected = max(candidates, key=lambda row: (row['date_to'], row['id'])) if candidates else None
    if selected:
        ident = str(int(selected['id']))
        selected['basis'] = json.loads(query("SELECT jsonb_build_object("
            "'contract_id',s.contract_id,'current_contract_wage',c.wage::text,'current_contract_write_date',c.write_date,"
            "'worked_days',(SELECT coalesce(jsonb_agg(jsonb_build_object('id',w.id,'type_id',w.work_entry_type_id,'code',t.code,'days',w.number_of_days::text,'hours',w.number_of_hours::text,'amount',w.amount::text) ORDER BY w.id),'[]') FROM hr_payslip_worked_days w JOIN hr_work_entry_type t ON t.id=w.work_entry_type_id WHERE w.payslip_id=s.id),"
            "'inputs',(SELECT coalesce(jsonb_agg(jsonb_build_object('id',i.id,'type_id',i.input_type_id,'code',t.code,'amount',i.amount::text) ORDER BY i.id),'[]') FROM hr_payslip_input i JOIN hr_payslip_input_type t ON t.id=i.input_type_id WHERE i.payslip_id=s.id)) "
            "FROM hr_payslip s LEFT JOIN hr_contract c ON c.id=s.contract_id WHERE s.id=" + ident))
    rules = json.loads(query("SELECT coalesce(jsonb_agg(jsonb_build_object('id',r.id,'code',r.code,'structure_id',r.struct_id,'active',r.active,'sequence',r.sequence,'category_id',r.category_id,'condition_select',r.condition_select,'amount_select',r.amount_select,'body',r.amount_python_compute,'write_date',r.write_date,'xmlids',(SELECT coalesce(jsonb_agg(d.module||'.'||d.name ORDER BY d.module,d.name),'[]') FROM ir_model_data d WHERE d.model='hr.salary.rule' AND d.res_id=r.id)) ORDER BY r.id),'[]') FROM hr_salary_rule r WHERE r.code IN ('BASIC','GROSS','NET')"))
    for rule in rules:
        rule['body_sha256'] = hashlib.sha256((rule.pop('body') or '').encode()).hexdigest()
    result = {'reference': 'sys_user_approved', 'read_only': True, 'orm_reads': False,
              'payroll_computed': False, 'employee_data_exported': False, 'formula_bodies_exported': False,
              'financial_certified': False, 'identity_conversion': False,
              'provider_license': manifest['license'], 'provider_version': manifest['version'],
              'snapshot_sha256': hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest(),
              'closed_slips': len(indexed), 'unambiguous_complete_slips': len(complete),
              'incomplete_slip_ids': incomplete, 'ambiguous_concepts': ambiguous,
              'essential_rule_origins': rules, 'selected_case': selected}
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'read_only': True, 'closed_slips': len(indexed),
                      'unambiguous_complete_slips': len(complete), 'ambiguous_concepts': len(ambiguous),
                      'incomplete_slips': len(incomplete),
                      'selected_period': selected['date_to'][:7] if selected else None}))


if __name__ == '__main__':
    main()
