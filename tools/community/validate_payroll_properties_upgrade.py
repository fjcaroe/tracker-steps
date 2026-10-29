"""Rehearse API 1.9/Base 1.2 -> API 1.10/Base 1.3 on a NEW Community D clone.

No active service, production access, module-state rewrite or source-D write.
The fixture uses the actual OCA engine and captures closed payroll with SQL;
upgraded historical amounts are never reconstructed from current contracts.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from datetime import datetime, timezone


SOURCE_DB = 'COMMUNITY_PAYROLL_API_CONFIGURATION_20261029D'
SOURCE_ROOT = Path('/opt/steps-validation/community-original-configuration-20261029D')
OFFICIAL_PIN = '4b4efe68291d6def5bb7d2e1f2b829e0cda577d4'
OCA_PIN = '4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e'
VERSIONS = {'step_payroll_oca_api': ('18.0.1.9.0', '18.0.1.10.0'),
            'step_simpledigital_oca_base': ('18.0.1.2.0', '18.0.1.3.0')}
DATABASE_PATTERN = r'COMMUNITY_PAYROLL_API_PROPERTIES_UPGRADE_[A-Za-z0-9_]+'
RAW_TABLES = ('hr_payslip', 'hr_payslip_line', 'hr_payslip_worked_days', 'hr_payslip_input',
              'account_move', 'account_move_line', 'hr_contract', 'hr_employee',
              'hr_salary_rule', 'hr_salary_rule_category', 'hr_payroll_structure',
              'hr_payroll_structure_type', 'hr_payslip_input_type', 'account_journal',
              'account_account', 'account_analytic_account', 'account_analytic_plan', 'account_analytic_line',
              'hr_work_entry', 'ir_sequence')
RELATIONS = ('hr_structure_salary_rule_rel', 'hr_payroll_structure_hr_payslip_input_type_rel',
             'hr_payroll_structure_hr_work_entry_type_rel')
CONFIG_XML = 'data/hr_salary_structure.xml'
CONFIG_XML_SHA256 = 'a736508a6ad2cd39bfdd184383f88da38fb1d2dbac00e99b954f2e3e902d3166'
CONFIG_ALIASES = {
    'structure_chile': ('hr_payroll_structure', 'hr.payroll.structure'),
    'structure_type_chile': ('hr_payroll_structure_type', 'hr.payroll.structure.type'),
}


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def identifier(name):
    assert re.fullmatch(r'[a-z_][a-z0-9_]*', name), 'Unsafe SQL identifier'
    return '"' + name + '"'


def readonly_sql(database, query):
    assert database == 'postgres' or database == SOURCE_DB or re.fullmatch(DATABASE_PATTERN, database)
    assert query.lstrip().upper().startswith(('SELECT ', 'SHOW ')), 'Read-only SELECT/SHOW required'
    return run('sudo', '-u', 'postgres', 'env', 'PGOPTIONS=-c default_transaction_read_only=on',
        'psql', '-XAtq', '-v', 'ON_ERROR_STOP=1', '-d', database,
        input='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\n' + query + ';\nROLLBACK;',
        text=True, capture_output=True).stdout.strip()


def file_manifest(path):
    assert path.is_dir()
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, default=str)


def raw_rows(env):
    """Stored rows only: no ORM reads of monetary or inherited rule fields."""
    result = {}
    for table in RAW_TABLES:
        env.cr.execute('SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY id),\'[]\'::jsonb) FROM '
                       + identifier(table) + ' t')
        result[table] = env.cr.fetchone()[0]
    result['relations'] = {}
    for table in RELATIONS:
        env.cr.execute('SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),\'[]\'::jsonb) FROM '
                       + identifier(table) + ' t')
        result['relations'][table] = env.cr.fetchone()[0]
    env.cr.execute("SELECT id,model,name FROM ir_model_fields WHERE model IN "
                   "('hr.payslip','hr.payslip.line','hr.payslip.worked_days','hr.payslip.input',"
                   "'hr.salary.rule','hr.payroll.structure','hr.payroll.structure.type','hr.payslip.input.type') ORDER BY id")
    result['field_ids'] = [dict(zip(('id', 'model', 'name'), row)) for row in env.cr.fetchall()]
    env.cr.execute("SELECT id,model FROM ir_model WHERE model IN "
                   "('hr.payslip','hr.payslip.line','hr.payslip.worked_days','hr.payslip.input',"
                   "'hr.salary.rule','hr.payroll.structure','hr.payroll.structure.type','hr.payslip.input.type') ORDER BY id")
    result['model_ids'] = [dict(zip(('id', 'model'), row)) for row in env.cr.fetchall()]
    env.cr.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                   "WHERE n.nspname='public' AND c.relkind='S' AND c.relname ~ '^ir_sequence_[0-9]+$' ORDER BY c.relname")
    names = [row[0] for row in env.cr.fetchall()]
    result['business_sequences'] = {}
    for name in names:
        env.cr.execute('SELECT last_value,is_called FROM ' + identifier(name))
        result['business_sequences'][name] = list(env.cr.fetchone())
    env.cr.execute("SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns "
                   "WHERE table_schema='public' AND table_name IN ('hr_salary_rule','hr_payslip_line') "
                   "AND column_name IN ('note','analytic_account_id') ORDER BY table_name,column_name")
    result['property_columns'] = [dict(zip(('table', 'field', 'data_type', 'is_nullable'), row)) for row in env.cr.fetchall()]
    env.cr.execute("SELECT id,module,name,model,res_id,noupdate FROM ir_model_data "
        "WHERE module='l10n_cl_simpledigital_payroll' AND name IN ('structure_chile','structure_type_chile') ORDER BY name")
    result['xml_config_aliases'] = [dict(zip(('id', 'module', 'name', 'model', 'res_id', 'noupdate'), row)) for row in env.cr.fetchall()]
    return result


def utc_datetime(value):
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def configuration_reload_allowlist(before, after, audit):
    """Explicit audit exception for two unchanged XML configuration records."""
    assert re.fullmatch(DATABASE_PATTERN, audit['database'])
    assert audit['license'] == 'AGPL-3'
    for key in ('approved_xml_sha256', 'legacy_xml_sha256', 'candidate_xml_sha256', 'package_xml_sha256'):
        assert audit[key] == CONFIG_XML_SHA256, 'XML configuration source pin changed'
    for key in ('source_pin_manifest_sha256', 'package_files_sha256', 'upgrade_log_sha256',
                'sql_clock_before_sha256', 'sql_clock_after_sha256'):
        assert re.fullmatch('[0-9a-f]{64}', audit[key]), 'Missing source/log provenance hash'
    assert audit['clock_source'] == 'PostgreSQL clock_timestamp AT TIME ZONE UTC'
    assert utc_datetime(audit['sql_utc_before']) <= utc_datetime(audit['sql_utc_after'])
    assert audit['reload_log_lines'] and all(audit['database'] in line and
        'odoo.modules.loading: loading l10n_cl_simpledigital_payroll/' + CONFIG_XML in line
        for line in audit['reload_log_lines']), 'Actual XML reload not witnessed'
    original = before['xml_config_aliases']
    assert original == after['xml_config_aliases'] == audit['aliases_before'], 'Original XML identity or noupdate changed'
    assert len(original) == 2 and {row['name'] for row in original} == set(CONFIG_ALIASES)
    allowed = set()
    for row in original:
        table, model = CONFIG_ALIASES[row['name']]
        assert row['module'] == 'l10n_cl_simpledigital_payroll' and row['model'] == model
        assert row['noupdate'] is False and type(row['id']) is int and type(row['res_id']) is int
        assert any(value['id'] == row['res_id'] for value in before[table]), 'XML master missing before upgrade'
        allowed.add((table, row['res_id']))
    return allowed


def verify_rows(before, after, xml_audit=None):
    """Preserve values; optionally audit two precisely witnessed loader dates.

    Omitting xml_audit retains strict comparison, including every timestamp.
    No payroll, accounting, other master timestamp or write_uid is exempted.
    """
    checked = 0
    allowed = configuration_reload_allowlist(before, after, xml_audit) if xml_audit else set()
    date_changes = []
    for table in RAW_TABLES:
        original = {row['id']: row for row in before[table]}
        current = {row['id']: row for row in after[table]}
        assert set(original) == set(current), 'Row identities changed: ' + table
        for row_id, row in original.items():
            now = current[row_id]
            for name, value in row.items():
                assert name in now, 'Original column missing: ' + table + '.' + name
                actual = now.get(name)
                if table == 'hr_salary_rule' and name == 'note':
                    expected = None if value is None else {'en_US': value}
                    assert actual == expected, 'Rule note did not preserve original HTML/NULL'
                elif table == 'hr_salary_rule' and name == 'analytic_account_id':
                    if value is None:
                        expected = None
                    else:
                        assert type(value) is int and value > 0 and row.get('company_id'), 'Ambiguous scalar analytic owner'
                        expected = {str(row['company_id']): value}
                    assert actual == expected, 'Rule analytic value/owner/NULL changed'
                elif name == 'write_date' and actual != value and (table, row_id) in allowed:
                    assert value is not None and actual is not None
                    assert utc_datetime(xml_audit['sql_utc_before']) <= utc_datetime(actual) <= utc_datetime(xml_audit['sql_utc_after']), 'Configuration date outside SQL upgrade window'
                    date_changes.append({'table': table, 'field': name, 'id': row_id})
                else:
                    assert name in now and actual == value, 'Original stored field changed: ' + table + '.' + name
            checked += 1
    if xml_audit:
        assert len(date_changes) == 2, 'Both expected XML loader dates must be witnessed'
    for key in ('model_ids', 'business_sequences', 'relations'):
        assert before[key] == after[key], 'Original identities or numbering changed: ' + key
    if 'xml_config_aliases' in before:
        assert before['xml_config_aliases'] == after['xml_config_aliases'], 'Original configuration XML aliases changed'
    current_fields = {(row['model'], row['name']): row['id'] for row in after['field_ids']}
    assert all(current_fields.get((row['model'], row['name'])) == row['id'] for row in before['field_ids']), 'Original field IDs changed'
    columns = {(row['table'], row['field']): row for row in after['property_columns']}
    for table, field, kind in (('hr_salary_rule', 'note', 'jsonb'), ('hr_salary_rule', 'analytic_account_id', 'jsonb'),
                               ('hr_payslip_line', 'note', 'text'), ('hr_payslip_line', 'analytic_account_id', 'integer')):
        assert columns[(table, field)]['data_type'] == kind, 'Unexpected master/line property storage'
    return {'raw_rows_compared': checked, 'raw_rows_preserved': checked - len(date_changes),
            'all_original_raw_fields_exact': all(before[table] == after[table] for table in RAW_TABLES),
            'expected_write_date_changes': len(date_changes), 'expected_write_date_change_records': date_changes,
            'write_date_exception_justification': 'Only the two pinned original XML configuration masters were rewritten with unchanged data by the real module loader inside the SQL UTC upgrade window.' if date_changes else None,
            'model_ids_preserved': len(before['model_ids']),
            'field_ids_preserved': len(before['field_ids']), 'historical_line_text_and_scalar_preserved': True,
            'rule_note_html_and_analytic_values_preserved': True, 'business_sequences_preserved': True}


def exercise(env, mode, directory):
    """Payload for the real Odoo shell, on the newly restored database only."""
    assert re.fullmatch(DATABASE_PATTERN, env.cr.dbname), 'Private upgrade clone required'
    root = Path(directory)
    from odoo import api, fields
    env = api.Environment(env.cr, env.uid, dict(env.context, tracking_disable=True,
        mail_create_nosubscribe=True, mail_notify_force_send=False), su=env.su)
    if mode == 'seed':
        from odoo.addons.step_payroll_contracts.testing import PayrollContractMixin
        from unittest.mock import patch
        class FixtureBase:
            @classmethod
            def setUpClass(cls):
                pass
        class Fixture(PayrollContractMixin, FixtureBase):
            payroll_group = 'payroll.group_payroll_manager'
            oca = True
        # Flush actual company chart callbacks, as TransactionCase does. No
        # payroll method, account operation, model or permission is mocked.
        company_class = type(env['res.company'])
        original_create = company_class.create
        def create_ready_company(records, values):
            company = original_create(records, values)
            records.env.cr.flush()
            return company
        Fixture.env = env
        with patch.object(company_class, 'create', create_ready_company):
            Fixture.setUpClass()
        case = Fixture()
        assert not case.scope.su
        case.contract.write({'date_start': fields.Date.today().replace(day=1)})
        # Provision configuration as fixture author, without granting analytic
        # creation rights to the payroll actor. Actual use checks remain normal.
        # The effective account must be readable; plan management is not part
        # of this normal posting role, as in the accepted functional cases.
        plan = env['account.analytic.plan'].create({
            'name': 'Private property upgrade analytic plan', 'default_applicability': 'optional'})
        analytic = env['account.analytic.account'].create({
            'name': 'Private property upgrade analytic account', 'plan_id': plan.id,
            'company_id': case.company.id}).with_env(case.scope)
        analytic.check_access('read')
        case.rule.write({'code': 'BASIC', 'note': '<p>Nota histórica: acentos, 0 y espacios internos.</p>',
                         'analytic_account_id': analytic.id})
        assert case.rule.company_id == case.company, 'Fixture must have its explicit original company'
        gross = case.rule.copy({'code': 'GROSS', 'sequence': 2, 'note': False, 'analytic_account_id': False,
            'account_debit': False, 'account_credit': False,
            'amount_python_compute': "result = result_rules['BASIC']['total']"})
        net = case.rule.copy({'code': 'NET', 'sequence': 3, 'note': False, 'analytic_account_id': False,
            'account_debit': False, 'account_credit': False,
            'amount_python_compute': "result = result_rules['GROSS']['total']"})
        slip = case.slip()
        kind = case.scope['hr.work.entry.type'].create({'name': 'Private upgrade attendance', 'code': 'PRIVATE_PROPERTY_UPGRADE'})
        day = case.scope['hr.payslip.worked_days'].create({'name': kind.name, 'code': kind.code,
            'payslip_id': slip.id, 'contract_id': case.contract.id, 'work_entry_type_id': kind.id,
            'number_of_days': 2, 'number_of_hours': 16})
        slip.compute_sheet()
        primary_lines = slip.line_ids.filtered(lambda line: line.salary_rule_id == case.rule)
        assert primary_lines
        # OCA's line dictionary does not copy these two inherited fields.
        # Enter the synthetic metadata normally while the actual slip is draft.
        primary_lines.write({'note': case.rule.note, 'analytic_account_id': analytic.id})
        # This existing OCA option confirms the already calculated draft;
        # otherwise confirmation would legitimately replace its draft lines.
        slip.prevent_compute_on_confirm = True
        amounts = {name: slip[name] for name in ('basic_wage', 'gross_wage', 'net_wage')}
        day_values = {'amount': day.amount, 'is_paid': day.is_paid}
        slip.action_payslip_done()
        assert slip.move_id and slip.state == 'done', 'Actual OCA posting did not create its entry'
        if slip.move_id.state != 'posted':
            slip.move_id.action_post()
        env.flush_all()
        # The legacy security provider deliberately forbids paid changes after
        # done. This marker is NOT a payment workflow: it is authorized only on
        # this just-created synthetic clone row, before its preservation seal.
        env.cr.execute("SELECT id,employee_id,contract_id,company_id,state,step_history_locked,paid "
            "FROM hr_payslip WHERE id=%s", (slip.id,))
        found = env.cr.fetchone()
        assert found is not None, 'Synthetic payslip disappeared before marker'
        marker_before = dict(zip(('id', 'employee_id', 'contract_id', 'company_id',
                                  'state', 'step_history_locked', 'paid'), found))
        write_private(root / 'synthetic-paid-marker-before.json', dict(marker_before,
            synthetic_fixture_only=True, database=env.cr.dbname,
            original_not_paid_predicate_matches=marker_before['paid'] is False,
            null_aware_predicate_matches=marker_before['paid'] is not True))
        assert (marker_before['employee_id'], marker_before['contract_id'], marker_before['company_id']) == (
            case.employee.id, case.contract.id, case.company.id), 'Synthetic marker identity mismatch'
        assert marker_before['state'] == 'done' and marker_before['step_history_locked'] is True, 'Actual closed-history guard missing'
        assert marker_before['paid'] is None or marker_before['paid'] is False, 'Synthetic row is already marked paid'
        # OCA's optional Boolean has no default. An omitted value may be SQL
        # NULL (ORM False); SQL NOT paid rejects that row. Keep the closed-state
        # guard exact and admit only False/NULL, never an existing True marker.
        env.cr.execute("UPDATE hr_payslip SET paid=true WHERE id=%s AND employee_id=%s "
            "AND contract_id=%s AND company_id=%s AND state='done' AND step_history_locked=true AND paid IS NOT TRUE",
            (slip.id, case.employee.id, case.contract.id, case.company.id))
        assert env.cr.rowcount == 1, 'Synthetic paid marker refused'
        slip.invalidate_recordset(['paid'])
        # Make an accidental closed recomputation observable. This legitimate
        # current-contract edit must not replace the previously closed values.
        case.contract.write({'wage': 1200000})
        env.flush_all()
        rows = raw_rows(env)
        selected = next(row for row in rows['hr_payslip'] if row['id'] == slip.id)
        assert selected['paid'] and selected['step_history_locked'], 'History must be locked by the real closing flow'
        assert all(selected[name] == value for name, value in amounts.items()), 'Closing changed authentic draft amounts'
        stored_day = next(row for row in rows['hr_payslip_worked_days'] if row['id'] == day.id)
        assert all(stored_day[name] == value for name, value in day_values.items())
        entry = next(row for row in rows['account_move'] if row['id'] == selected['move_id'])
        lines = [row for row in rows['account_move_line'] if row['move_id'] == entry['id']]
        assert entry['state'] == 'posted' and len(lines) >= 2 and sum(row['debit'] for row in lines) > 0
        assert abs(sum(row['debit'] - row['credit'] for row in lines)) < 0.00001, 'Actual entry does not balance'
        historical = [row for row in rows['hr_payslip_line'] if row['slip_id'] == slip.id and row['salary_rule_id'] == case.rule.id]
        assert historical and all(isinstance(row['note'], str) and row['note'] and row['analytic_account_id'] == analytic.id for row in historical), 'Legacy history fixture lacks scalar properties'
        columns = {(row['table'], row['field']): row['data_type'] for row in rows['property_columns']}
        assert columns == {('hr_salary_rule', 'note'): 'text', ('hr_salary_rule', 'analytic_account_id'): 'integer',
                           ('hr_payslip_line', 'note'): 'text', ('hr_payslip_line', 'analytic_account_id'): 'integer'}
        seed = {'synthetic_fixture_only': True, 'real_oca_engine': True, 'normal_actor': True,
            'actor': case.scope.uid, 'company': case.company.id, 'contract': case.contract.id,
            'rule': case.rule.id, 'null_rules': [gross.id, net.id], 'analytic': analytic.id,
            'slip': slip.id, 'day': day.id, 'move': entry['id'], 'draft_amounts': amounts,
            'draft_day_values': day_values, 'raw_rows': rows,
            'synthetic_paid_marker': True, 'payment_workflow_certified': False,
            'synthetic_paid_marker_original_sql_value': marker_before['paid'],
            'synthetic_paid_marker_witness_sha256': hashlib.sha256((root / 'synthetic-paid-marker-before.json').read_bytes()).hexdigest(),
            'confirmation_uses_existing_oca_draft_option': True,
            'current_wage_changed_after_closure': True}
        write_private(root / 'seed.json', seed)
        env.cr.commit()
    elif mode == 'verify':
        seed = json.loads((root / 'seed.json').read_text())
        witness = (root / 'synthetic-paid-marker-before.json').read_bytes()
        assert hashlib.sha256(witness).hexdigest() == seed['synthetic_paid_marker_witness_sha256'], 'Synthetic marker witness changed'
        marker = json.loads(witness)
        assert marker['id'] == seed['slip'] and marker['state'] == 'done' and marker['step_history_locked'] is True
        assert marker['paid'] is None or marker['paid'] is False
        scope = api.Environment(env.cr, seed['actor'], dict(env.context, allowed_company_ids=[seed['company']]), su=False)
        assert not scope.su
        # Access checks do not ask computed monetary/inherited field values.
        scope['hr.payslip'].browse(seed['slip']).check_access('read')
        scope['hr.payslip.line'].browse([row['id'] for row in seed['raw_rows']['hr_payslip_line']
                                       if row['slip_id'] == seed['slip']]).check_access('read')
        before_read = raw_rows(env)
        xml_audit = json.loads((root / 'xml-config-upgrade-audit.json').read_text())
        assert hashlib.sha256((root / 'upgrade.log').read_bytes()).hexdigest() == xml_audit['upgrade_log_sha256']
        assert hashlib.sha256((root / 'package-files.json').read_bytes()).hexdigest() == xml_audit['package_files_sha256']
        pin_bytes = (root / 'xml-config-source-pin.json').read_bytes()
        assert hashlib.sha256(pin_bytes).hexdigest() == xml_audit['source_pin_manifest_sha256']
        pin = json.loads(pin_bytes)
        assert pin['license'] == 'AGPL-3' and pin['files'][CONFIG_XML] == CONFIG_XML_SHA256
        for phase in ('before', 'after'):
            clock_bytes = (root / ('upgrade-sql-clock-' + phase + '.json')).read_bytes()
            assert hashlib.sha256(clock_bytes).hexdigest() == xml_audit['sql_clock_' + phase + '_sha256']
            assert json.loads(clock_bytes)['utc'] == xml_audit['sql_utc_' + phase]
        proof = verify_rows(seed['raw_rows'], before_read, xml_audit)
        # The real historical read API is required to use stored values. No
        # current wage/amount getter and no compute_sheet invocation occurs.
        slip = scope['hr.payslip'].browse(seed['slip'])
        values = slip._get_line_values(['BASIC', 'GROSS', 'NET'])
        expected = {row['code']: row['total'] for row in seed['raw_rows']['hr_payslip_line'] if row['slip_id'] == seed['slip']}
        for code in ('BASIC', 'GROSS', 'NET'):
            assert values[code][slip.id]['total'] == expected[code], 'Historical API did not return stored totals'
        after_read = raw_rows(env)
        assert before_read == after_read, 'Historical read mutated stored payroll'
        write_private(root / 'rows-after.json', after_read)
        write_private(root / 'verified.json', dict(proof, actual_upgrade=True, normal_actor=True,
            real_oca_engine=True, historical_read_unchanged=True, closed_payroll_recomputed=False,
            synthetic_fixture_only=True, synthetic_paid_marker=True, payment_workflow_certified=False,
            synthetic_paid_marker_witness_sha256=seed['synthetic_paid_marker_witness_sha256'],
            synthetic_paid_marker_original_sql_value=seed['synthetic_paid_marker_original_sql_value'],
            current_wage_changed_after_closure=True,
            customer_payroll_certified=False, engine_conversion=False))
        env.cr.rollback()
    else:
        raise AssertionError('Unsupported private rehearsal payload')


def database_snapshot(database):
    """Source drift check: hashes only, including metadata and sequence values."""
    names = json.loads(readonly_sql(database, "SELECT coalesce(json_agg(c.relname ORDER BY c.relname),'[]'::json) "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p')"))
    result = {}
    for name in names:
        result[name] = json.loads(readonly_sql(database, "SELECT json_build_object('rows',count(*),'sha256',"
            "encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex')) FROM " + identifier(name) + ' t'))
    sequences = json.loads(readonly_sql(database, "SELECT coalesce(json_agg(c.relname ORDER BY c.relname),'[]'::json) "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='S'"))
    result['sequence_values'] = {name: readonly_sql(database, 'SELECT last_value::text||\':\'||is_called::text FROM ' + identifier(name)) for name in sequences}
    return result


def manifest(path):
    return ast.literal_eval((path / '__manifest__.py').read_text(encoding='utf-8-sig'))


def main():
    import configparser
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'candidate', 'runtime', 'oca'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-root', type=Path, default=SOURCE_ROOT)
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    assert hasattr(os, 'geteuid') and os.geteuid() == 0, 'Linux root execution required'
    import fcntl
    import pwd
    assert re.fullmatch(DATABASE_PATTERN, args.database)
    os.umask(0o077)
    root, source_root, candidate = args.root.resolve(), args.source_root.resolve(), args.candidate.resolve()
    assert Path('/opt/steps-validation') in root.parents and not root.exists()
    assert source_root == SOURCE_ROOT and Path('/opt/steps-validation') in candidate.parents
    assert source_root not in root.parents, 'Never place rehearsal artifacts inside accepted D'
    assert root != candidate and root not in candidate.parents and candidate not in root.parents
    acceptance_path = source_root / 'community/passed.json'
    accepted = json.loads(acceptance_path.read_text())
    assert accepted['database'] == SOURCE_DB and accepted['mode'] == 'community' and accepted['counts']['enterprise'] == 0
    assert accepted['official_community_revision'] == OFFICIAL_PIN and accepted['oca_revision'] == OCA_PIN
    assert hashlib.sha256((source_root / 'community/source-files.json').read_bytes()).hexdigest() == accepted['source_files_sha256']
    for relative, expected in json.loads((source_root / 'community/source-files.json').read_text()).items():
        assert hashlib.sha256((source_root / 'addons' / relative).read_bytes()).hexdigest() == expected, 'Accepted source addon drift'
    consumer_fingerprints = json.loads((source_root / 'community/consumer-source-files.json').read_text())
    for relative, expected in consumer_fingerprints.items():
        assert hashlib.sha256((source_root / 'community/consumer-addons' / relative).read_bytes()).hexdigest() == expected, 'Accepted consumer overlay drift'
    for folder, url, pin in ((args.runtime, 'https://github.com/odoo/odoo.git', OFFICIAL_PIN),
                              (args.oca, 'https://github.com/OCA/payroll.git', OCA_PIN)):
        assert run('git', '-C', str(folder), 'remote', 'get-url', 'origin', capture_output=True, text=True).stdout.strip() == url
        assert run('git', '-C', str(folder), 'rev-parse', 'HEAD', capture_output=True, text=True).stdout.strip() == pin
        assert not run('git', '-C', str(folder), 'status', '--porcelain', capture_output=True, text=True).stdout.strip()
    for module, versions in VERSIONS.items():
        assert manifest(candidate / module)['version'] == versions[1]
        assert any((candidate / module / 'migrations' / versions[1]).glob('pre-*.py')), 'Required pre-migration is not wired: ' + module
    config = configparser.ConfigParser(interpolation=None)
    assert config.read('/etc/dev_odoo18.conf')
    identity = pwd.getpwnam('odoo')
    source_store = source_root / 'community/data/filestore' / SOURCE_DB
    if source_store.exists():
        assert not source_store.is_symlink() and source_store.resolve().is_relative_to(source_root)
    roots = (source_root / 'community/consumer-addons', source_root / 'community/addons',
             args.oca, args.runtime / 'addons', args.runtime / 'odoo/addons')
    root.mkdir(mode=0o700); os.chown(root, identity.pw_uid, identity.pw_gid)
    probe_copy = root / 'upgrade-probe.py'
    with probe_copy.open('xb') as stream:
        stream.write(Path(__file__).read_bytes())
    with open('/run/lock/steps-environments.lock', 'a') as lease:
        print('PAYROLL_PROPERTIES_UPGRADE_WAITING_FOR_SHARED_LEASE', flush=True)
        fcntl.flock(lease, fcntl.LOCK_EX)
        assert not readonly_sql('postgres', "SELECT 1 FROM pg_database WHERE datname='" + args.database + "'")
        installed = json.loads(readonly_sql(SOURCE_DB, "SELECT json_agg(json_build_object('name',name,'version',latest_version,'license',license) ORDER BY name) FROM ir_module_module WHERE state='installed'"))
        assert not any(row['license'] == 'OEEL-1' for row in installed)
        deployed = {row['name']: row['version'] for row in installed}
        assert all(deployed.get(module) == versions[0] for module, versions in VERSIONS.items())
        assert {'payroll', 'payroll_account'} <= set(deployed), 'Actual OCA engine required'
        pgdir = Path(readonly_sql('postgres', 'SHOW data_directory'))
        size = int(readonly_sql('postgres', "SELECT pg_database_size('" + SOURCE_DB + "')"))
        def capacity(extra=False):
            pg = os.statvfs(pgdir); artifact = os.statvfs(root)
            value = {'postgres_available': pg.f_bavail * pg.f_frsize, 'artifacts_available': artifact.f_bavail * artifact.f_frsize}
            assert value['postgres_available'] >= 5 * 1024**3 + (2 * size if extra else 0), 'PostgreSQL/WAL reserve below 5 GiB plus restore estimate'
            assert value['artifacts_available'] >= 2 * 1024**3 + (size if extra else 0), 'Artifact reserve below 2 GiB plus dump estimate'
            return value
        write_private(root / 'storage-preflight.json', capacity(extra=True))
        source_before = database_snapshot(SOURCE_DB)
        write_private(root / 'source-before.json', source_before)
        source_store_before = file_manifest(source_store) if source_store.exists() else {}
        if not source_store.exists():
            assert readonly_sql(SOURCE_DB, "SELECT count(*) FROM ir_attachment WHERE store_fname IS NOT NULL") == '0', 'Missing accepted filestore'
        write_private(root / 'source-filestore.json', source_store_before)
        backup = root / 'source.dump'
        with backup.open('xb') as stream:
            os.chmod(backup, 0o600)
            run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', SOURCE_DB, stdout=stream)
        with backup.open('rb') as stream, (root / 'decode.log').open('x') as log:
            run('sudo', '-u', 'postgres', 'pg_restore', '--file=/dev/null', stdin=stream, stdout=log, stderr=subprocess.STDOUT)
        capacity()
        run('sudo', '-u', 'postgres', 'createdb', '--owner=' + config['options']['db_user'], args.database)
        with backup.open('rb') as stream, (root / 'restore.log').open('x') as log:
            run('sudo', '-u', 'postgres', 'pg_restore', '--exit-on-error', '--no-owner', '--no-acl', '--no-comments',
                '--no-tablespaces', '--role=' + config['options']['db_user'], '-d', args.database, stdin=stream,
                stdout=log, stderr=subprocess.STDOUT)
        # Neutralize the new clone only. No module state is rewritten.
        run('sudo', '-u', 'postgres', 'psql', '-Xq', '-v', 'ON_ERROR_STOP=1', '-d', args.database,
            input='UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;', text=True, capture_output=True)
        data = root / 'data'; store = data / 'filestore' / args.database
        store.parent.mkdir(parents=True)
        if source_store.exists():
            assert not any(p.is_symlink() for p in source_store.rglob('*')), 'Filestore symlinks refused'
            shutil.copytree(source_store, store)
        else:
            store.mkdir()
        assert file_manifest(store) == source_store_before
        legacy = root / 'legacy-addons'; upgraded = root / 'candidate-addons'
        legacy.mkdir(); upgraded.mkdir()
        files = {}
        for row in installed:
            module = row['name']
            assert re.fullmatch('[A-Za-z0-9_]+', module)
            provider = next((folder / module for folder in roots if (folder / module / '__manifest__.py').exists()), None)
            assert provider is not None, 'Missing accepted installed addon: ' + module
            assert manifest(provider).get('license') != 'OEEL-1'
            if provider.resolve().is_relative_to(source_root):
                shutil.copytree(provider, legacy / module, ignore=shutil.ignore_patterns('__pycache__'))
            else:
                (legacy / module).symlink_to(provider.resolve(), target_is_directory=True)
            if module in VERSIONS:
                assert manifest(legacy / module)['version'] == VERSIONS[module][0]
                shutil.copytree(candidate / module, upgraded / module, ignore=shutil.ignore_patterns('__pycache__'))
            else:
                (upgraded / module).symlink_to((legacy / module).resolve(), target_is_directory=True)
            files[module] = {'legacy': file_manifest(legacy / module), 'candidate': file_manifest(upgraded / module)}
        write_private(root / 'package-files.json', files)
        pin_path = candidate / 'tools/community/simpledigital_runtime_source.json'
        pin_bytes = pin_path.read_bytes()
        source_pin = json.loads(pin_bytes)
        assert source_pin['license'] == 'AGPL-3' and source_pin['files'][CONFIG_XML] == CONFIG_XML_SHA256
        assert manifest(legacy / 'l10n_cl_simpledigital_payroll')['license'] == 'AGPL-3'
        assert files['l10n_cl_simpledigital_payroll']['legacy'][CONFIG_XML] == CONFIG_XML_SHA256
        assert files['l10n_cl_simpledigital_payroll']['candidate'][CONFIG_XML] == CONFIG_XML_SHA256
        with (root / 'xml-config-source-pin.json').open('xb') as stream:
            stream.write(pin_bytes)
        for path in (root, *root.rglob('*')):
            if not path.is_symlink():
                os.chown(path, identity.pw_uid, identity.pw_gid)
                if path.is_file():
                    os.chmod(path, 0o600)
        def execute(label, overlay, flags=(), payload=None):
            command = ['sudo', '-u', 'odoo', '/usr/bin/python3.10', str(args.runtime / 'odoo-bin')]
            if payload is not None:
                command += ['shell']
            command += ['-c', '/etc/dev_odoo18.conf', '-d', args.database, '--db-filter=^' + args.database + '$',
                '--addons-path=' + str(overlay) + ',' + str(args.runtime / 'addons'), '--data-dir=' + str(data),
                '--load=base,web', '--workers=0', '--max-cron-threads=0', '--no-http', '--without-demo=all',
                '--logfile=' + str(root / (label + '.log')), *flags]
            with (root / (label + '-bootstrap.log')).open('x') as log:
                status = subprocess.run(command, input=payload, text=True, stdout=log, stderr=subprocess.STDOUT)
            logfile = root / (label + '.log')
            log = logfile.read_text(errors='replace') if logfile.exists() else ''
            assert status.returncode == 0 and not re.search(r' (ERROR|CRITICAL) ', log), 'Blocked; inspect private log: ' + str(logfile)
            capacity()
        probe = str(probe_copy)
        seed = "import runpy; runpy.run_path(" + repr(probe) + ")[\"exercise\"](env,\"seed\"," + repr(str(root)) + ')'
        execute('legacy-seed', legacy, payload=seed)
        assert (root / 'seed.json').exists(), 'Legacy fixture did not commit evidence'
        clock_query = "SELECT json_build_object('utc',clock_timestamp() AT TIME ZONE 'UTC')"
        clock_before = json.loads(readonly_sql(args.database, clock_query))
        write_private(root / 'upgrade-sql-clock-before.json', clock_before)
        execute('upgrade', upgraded, flags=('-u', ','.join(VERSIONS), '--stop-after-init'))
        clock_after = json.loads(readonly_sql(args.database, clock_query))
        write_private(root / 'upgrade-sql-clock-after.json', clock_after)
        actual = json.loads(readonly_sql(args.database, "SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE name IN ('step_payroll_oca_api','step_simpledigital_oca_base') AND state='installed'"))
        assert actual == {module: versions[1] for module, versions in VERSIONS.items()}, 'Upgrade versions not installed'
        reload_lines = [line for line in (root / 'upgrade.log').read_text().splitlines()
            if 'odoo.modules.loading: loading l10n_cl_simpledigital_payroll/' + CONFIG_XML in line]
        xml_audit = {'database': args.database, 'license': 'AGPL-3',
            'approved_xml_sha256': source_pin['files'][CONFIG_XML],
            'legacy_xml_sha256': files['l10n_cl_simpledigital_payroll']['legacy'][CONFIG_XML],
            'candidate_xml_sha256': files['l10n_cl_simpledigital_payroll']['candidate'][CONFIG_XML],
            'package_xml_sha256': files['l10n_cl_simpledigital_payroll']['candidate'][CONFIG_XML],
            'source_pin_manifest_sha256': hashlib.sha256(pin_bytes).hexdigest(),
            'package_files_sha256': hashlib.sha256((root / 'package-files.json').read_bytes()).hexdigest(),
            'upgrade_log_sha256': hashlib.sha256((root / 'upgrade.log').read_bytes()).hexdigest(),
            'sql_clock_before_sha256': hashlib.sha256((root / 'upgrade-sql-clock-before.json').read_bytes()).hexdigest(),
            'sql_clock_after_sha256': hashlib.sha256((root / 'upgrade-sql-clock-after.json').read_bytes()).hexdigest(),
            'clock_source': 'PostgreSQL clock_timestamp AT TIME ZONE UTC',
            'sql_utc_before': clock_before['utc'], 'sql_utc_after': clock_after['utc'],
            'reload_log_lines': reload_lines,
            'aliases_before': json.loads((root / 'seed.json').read_text())['raw_rows']['xml_config_aliases']}
        write_private(root / 'xml-config-upgrade-audit.json', xml_audit)
        for name in ('xml-config-upgrade-audit.json', 'upgrade-sql-clock-before.json', 'upgrade-sql-clock-after.json'):
            os.chown(root / name, identity.pw_uid, identity.pw_gid)
        verify = seed.replace('"seed"', '"verify"')
        execute('upgraded-verify', upgraded, payload=verify)
        assert (root / 'verified.json').exists(), 'Upgraded historical verification missing'
        assert readonly_sql(args.database, "SELECT count(*) FROM ir_module_module WHERE state='installed' AND license='OEEL-1'") == '0'
        source_after = database_snapshot(SOURCE_DB)
        write_private(root / 'source-after.json', source_after)
        assert source_after == source_before, 'Accepted source D changed'
        assert (file_manifest(source_store) if source_store.exists() else {}) == source_store_before, 'Source D filestore changed'
        assert all(file_manifest(legacy / module) == value['legacy'] and file_manifest(upgraded / module) == value['candidate']
                   for module, value in files.items()), 'Frozen upgrade code changed'
        proof = json.loads((root / 'verified.json').read_text())
        proof.update(source_database=SOURCE_DB, database=args.database, original_versions={m: v[0] for m, v in VERSIONS.items()},
            target_versions=actual, source_acceptance_sha256=hashlib.sha256(acceptance_path.read_bytes()).hexdigest(),
            source_snapshot_sha256=digest(source_after), source_unchanged=True, source_filestore_unchanged=True,
            backup_decoded=True, backup_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),
            package_files_sha256=digest(files), writes_to_source=False, module_states_rewritten=False,
            source_consumer_files_sha256=digest(consumer_fingerprints),
            seed_sha256=hashlib.sha256((root / 'seed.json').read_bytes()).hexdigest(),
            rows_after_sha256=hashlib.sha256((root / 'rows-after.json').read_bytes()).hexdigest(),
            xml_config_upgrade_audit_sha256=hashlib.sha256((root / 'xml-config-upgrade-audit.json').read_bytes()).hexdigest(),
            official_community_revision=OFFICIAL_PIN, oca_revision=OCA_PIN,
            tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), full_community_conversion=False)
        write_private(root / 'passed.json', proof)
        print(json.dumps({key: proof[key] for key in ('actual_upgrade', 'raw_rows_preserved', 'historical_read_unchanged',
            'source_unchanged', 'source_filestore_unchanged', 'backup_decoded', 'writes_to_source', 'full_community_conversion')}))


if __name__ == '__main__':
    main()
