"""Rehearse the fixed admission or period upgrade on a NEW accepted F/C clone.

This is not an original-configuration adoption or a payment certification.
The old properties-upgrade helper remains byte-identical and is copied beside
the private probe, with a sealed hash, to reuse its read-only snapshot/audit API.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


SOURCE_DB = 'COMMUNITY_PAYROLL_API_PROPERTIES_20261029F'
SOURCE_ROOT = Path('/opt/steps-validation/community-payroll-properties-20261029F')
DATABASE_PATTERN = r'COMMUNITY_PAYROLL_API_ADMISSION_UPGRADE_[A-Za-z0-9_]+'
VERSIONS = {'step_payroll_oca_api': ('18.0.1.10.0', '18.0.1.11.0'),
            'step_simpledigital_oca_base': ('18.0.1.3.0', '18.0.1.4.0')}
HELPER_NAME = 'validate_payroll_properties_upgrade.py'
HELPER_PATH = Path(__file__).resolve().with_name(HELPER_NAME)
spec = importlib.util.spec_from_file_location('_admission_properties_dependency', HELPER_PATH)
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
# This isolated module instance never mutates the imported old runner or its
# files. Bind only private-database guards for its public SQL/audit helpers.
common.SOURCE_DB, common.SOURCE_ROOT = SOURCE_DB, SOURCE_ROOT
common.DATABASE_PATTERN = DATABASE_PATTERN
run, digest, identifier = common.run, common.digest, common.identifier
readonly_sql, database_snapshot = common.readonly_sql, common.database_snapshot
file_manifest, write_private, manifest = common.file_manifest, common.write_private, common.manifest
RAW_TABLES, RELATIONS = common.RAW_TABLES, common.RELATIONS
OFFICIAL_PIN, OCA_PIN = common.OFFICIAL_PIN, common.OCA_PIN
CONFIG_XML, CONFIG_XML_SHA256 = common.CONFIG_XML, common.CONFIG_XML_SHA256
DERIVED_CONFIG_XML_SHA256 = common.DERIVED_CONFIG_XML_SHA256
PROVIDER_BUILDER_SHA256 = common.PROVIDER_BUILDER_SHA256
PROVIDER_DERIVATION_SHA256 = common.PROVIDER_DERIVATION_SHA256
PROVIDER_SOURCE_FILES_SHA256 = common.PROVIDER_SOURCE_FILES_SHA256
NEW_FIELDS = {('hr.payroll.structure', 'unpaid_work_entry_type_ids'),
    ('hr.salary.rule', 'debit_tag_ids'), ('hr.salary.rule', 'credit_tag_ids'),
    ('hr.payslip.line', 'debit_tag_ids'), ('hr.payslip.line', 'credit_tag_ids')}
ADMISSION_NEW_FIELDS = frozenset(NEW_FIELDS)
UPGRADE_PROFILE = 'admission'
SOURCE_INSTALLED_COUNT = 95


def configure_profile(name):
    """Fixed accepted private baselines only; never arbitrary source DBs."""
    global SOURCE_DB, SOURCE_ROOT, VERSIONS, NEW_FIELDS, UPGRADE_PROFILE, SOURCE_INSTALLED_COUNT
    if name == 'admission':
        database = 'COMMUNITY_PAYROLL_API_PROPERTIES_20261029F'
        root = Path('/opt/steps-validation/community-payroll-properties-20261029F')
        versions = {'step_payroll_oca_api': ('18.0.1.10.0', '18.0.1.11.0'),
                    'step_simpledigital_oca_base': ('18.0.1.3.0', '18.0.1.4.0')}
        new_fields = set(ADMISSION_NEW_FIELDS)
    elif name == 'period':
        database = 'COMMUNITY_PAYROLL_API_ADMISSION_20261029C'
        root = Path('/opt/steps-validation/community-payroll-admission-20261029C')
        versions = {'step_payroll_oca_api': ('18.0.1.11.0', '18.0.1.11.0'),
                    'step_simpledigital_oca_base': ('18.0.1.4.0', '18.0.1.5.0')}
        new_fields = set()
    elif name == 'name-scalar':
        database = 'COMMUNITY_PAYROLL_API_PERIOD_20261029C'
        root = Path('/opt/steps-validation/community-payroll-period-20261029C')
        versions = {'step_payroll_oca_api': ('18.0.1.11.0', '18.0.1.12.0'),
                    'step_simpledigital_oca_base': ('18.0.1.5.0', '18.0.1.5.0')}
        new_fields = set()
    elif name == 'saved-inputs':
        database = 'COMMUNITY_PAYROLL_API_SCHEMA_20261029B'
        root = Path('/opt/steps-validation/community-payroll-schema-20261029B')
        versions = {'step_payroll_oca_api': ('18.0.1.12.0', '18.0.1.13.0'),
                    'step_simpledigital_oca_base': ('18.0.1.5.0', '18.0.1.6.0'),
                    'step_simpledigital_oca_security': ('18.0.1.6.0', '18.0.1.7.0')}
        new_fields = set()
    else:
        raise ValueError('Unknown fixed private upgrade profile')
    SOURCE_DB, SOURCE_ROOT, VERSIONS, NEW_FIELDS = database, root, versions, new_fields
    common.SOURCE_DB, common.SOURCE_ROOT = SOURCE_DB, SOURCE_ROOT
    UPGRADE_PROFILE = name
    SOURCE_INSTALLED_COUNT = 96 if name in ('name-scalar', 'saved-inputs') else 95


def raw_rows(env):
    result = common.raw_rows(env)
    # No records, computes, defaults or rule bodies are read through the ORM.
    for key, query in (
        ('all_field_ids', 'SELECT id,model,name FROM ir_model_fields ORDER BY id'),
        ('all_model_ids', 'SELECT id,model FROM ir_model ORDER BY id')):
        env.cr.execute(query)
        names = [column[0] for column in env.cr.description]
        result[key] = [dict(zip(names, row)) for row in env.cr.fetchall()]
    env.cr.execute("SELECT is_nullable FROM information_schema.columns WHERE table_schema='public' "
        "AND table_name='hr_payroll_structure_type' AND column_name='name'")
    row = env.cr.fetchone()
    assert row, 'Original structure type name column missing'
    result['structure_type_name_nullable'] = row[0]
    env.cr.execute("""SELECT c.relname,a.attname,f.relname,fa.attname,k.confdeltype
        FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_class f ON f.oid=k.confrelid
        JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.conkey[1]
        JOIN pg_attribute fa ON fa.attrelid=f.oid AND fa.attnum=k.confkey[1]
        WHERE n.nspname='public' AND k.contype='f' AND array_length(k.conkey,1)=1
        AND c.relname IN ('hr_salary_rule','hr_payslip_line') AND a.attname='category_id'
        ORDER BY c.relname""")
    result['category_foreign_keys'] = [list(row) for row in env.cr.fetchall()]
    if UPGRADE_PROFILE == 'name-scalar':
        env.cr.execute("SELECT data_type,is_nullable,column_default FROM information_schema.columns "
                       "WHERE table_schema='public' AND table_name='hr_payslip_input_type' AND column_name='name'")
        result['input_name_column'] = list(env.cr.fetchone())
    return result


def verify_rows(before, after, xml_audit=None):
    """Keep history/JSON exact; permit only the explicitly admitted name wrapper."""
    allowed = common.configuration_reload_allowlist(before, after, xml_audit) if xml_audit else set()
    date_changes, input_name_changes, checked = [], [], 0
    for table in RAW_TABLES:
        original = {row['id']: row for row in before[table]}
        current = {row['id']: row for row in after[table]}
        assert original.keys() == current.keys(), 'Row identities changed: ' + table
        for ident, row in original.items():
            for name, value in row.items():
                now = current[ident]
                assert name in now, 'Original stored column missing: ' + table + '.' + name
                if name == 'write_date' and value != now[name] and (table, ident) in allowed:
                    assert value is not None and now[name] is not None
                    assert common.utc_datetime(xml_audit['sql_utc_before']) <= common.utc_datetime(now[name]) <= common.utc_datetime(xml_audit['sql_utc_after']), 'Configuration date outside SQL upgrade window'
                    date_changes.append({'table': table, 'field': name, 'id': ident})
                elif (UPGRADE_PROFILE == 'name-scalar' and table == 'hr_payslip_input_type'
                      and name == 'name' and isinstance(value, dict)):
                    assert set(value) == {'en_US'} and isinstance(value['en_US'], str), 'Unadmitted original input translation'
                    assert type(now[name]) is str and now[name] == value['en_US'], 'Original input literal changed'
                    input_name_changes.append({'table': table, 'field': name, 'id': ident,
                        'source_sha256': digest(value), 'literal_sha256': digest(now[name])})
                else:
                    assert digest(now[name]) == digest(value), 'Original stored field changed: ' + table + '.' + name
            checked += 1
    if xml_audit:
        assert len(date_changes) == 2, 'Both approved XML loader dates must be witnessed'
    for key in ('relations', 'business_sequences', 'model_ids', 'all_model_ids', 'xml_config_aliases', 'property_columns'):
        assert before[key] == after[key], 'Original storage or identity changed: ' + key
    assert all(before['relations'][name] for name in RELATIONS), 'All three existing relations need real members'
    for key in ('field_ids', 'all_field_ids'):
        current = {(row['model'], row['name']): row['id'] for row in after[key]}
        assert all(current.get((row['model'], row['name'])) == row['id'] for row in before[key]), 'Original field PK changed'
    columns = {(row['table'], row['field']): row['data_type'] for row in after['property_columns']}
    assert columns == {('hr_salary_rule', 'note'): 'jsonb', ('hr_salary_rule', 'analytic_account_id'): 'jsonb',
        ('hr_payslip_line', 'note'): 'text', ('hr_payslip_line', 'analytic_account_id'): 'integer'}, 'Historical property storage changed'
    assert after['structure_type_name_nullable'] == 'NO', 'Original type name is not physically NOT NULL'
    assert after['category_foreign_keys'] == [
        ['hr_payslip_line', 'category_id', 'hr_salary_rule_category', 'id', 'n'],
        ['hr_salary_rule', 'category_id', 'hr_salary_rule_category', 'id', 'r']], 'Original category delete contracts not installed'
    assert all(row.get('name') is not None for row in after['hr_payroll_structure_type']), 'Original type names were not admitted'
    old_fields = {(row['model'], row['name']) for row in before['all_field_ids']}
    new_fields = [row for row in after['all_field_ids'] if (row['model'], row['name']) not in old_fields]
    assert {(row['model'], row['name']) for row in new_fields} == NEW_FIELDS, 'Unexpected or missing new admission fields'
    result = {'raw_rows_compared': checked, 'raw_rows_preserved': checked - len(date_changes) - len(input_name_changes),
        'all_original_raw_fields_exact': all(digest(before[t]) == digest(after[t]) for t in RAW_TABLES),
        'expected_write_date_changes': len(date_changes), 'expected_write_date_change_records': date_changes,
        'write_date_exception_justification': 'Only the two pinned original XML configuration masters were rewritten with unchanged data by the real module loader inside the SQL UTC upgrade window.' if date_changes else None,
        'model_ids_preserved': len(before['all_model_ids']), 'field_ids_preserved': len(before['all_field_ids']),
        'new_fields': new_fields, 'existing_relations_preserved': len(RELATIONS), 'existing_relations_nonempty': True,
        'business_sequences_preserved': True, 'historical_line_text_and_scalar_preserved': True,
        'rule_note_html_and_analytic_values_preserved': True, 'rule_json_properties_preserved_exactly': True,
        'structure_type_name_not_null': True, 'rule_category_ondelete': 'restrict', 'line_category_ondelete': 'set null'}
    if UPGRADE_PROFILE == 'name-scalar':
        assert before['input_name_column'] == ['jsonb', 'NO', None]
        assert after['input_name_column'] == ['character varying', 'NO', None]
        assert input_name_changes, 'Actual nonempty input-name conversion must be witnessed'
        assert any(isinstance(row.get('note'), dict) and {'en_US', 'es_CL'} <= row['note'].keys()
                   and row['note']['en_US'] != row['note']['es_CL'] for row in before['hr_salary_rule']), 'Distinct stored note translations must be witnessed'
        result.update(input_name_projection_records=input_name_changes,
                      input_name_literal_values_preserved=True, input_name_not_null_preserved=True,
                      input_name_sql_default_absent=True, multilingual_rule_note_preserved=True)
    return result


def offline_command(runtime, overlay, data, database, logfile, flags=(), shell=False):
    assert re.fullmatch(DATABASE_PATTERN, database), 'Private admission clone required'
    command = ['unshare', '--net', '--', 'sudo', '-u', 'odoo', '/usr/bin/python3.10', str(runtime / 'odoo-bin')]
    if shell:
        command.append('shell')
    return command + ['-c', '/etc/dev_odoo18.conf', '-d', database, '--db-filter=^' + database + '$',
        '--db_host=/var/run/postgresql', '--addons-path=' + str(overlay) + ',' + str(runtime / 'addons'),
        '--data-dir=' + str(data), '--load=base,web', '--workers=0', '--max-cron-threads=0',
        '--no-http', '--without-demo=all', '--logfile=' + str(logfile), *flags]


def verify_dependency(directory):
    root = Path(directory)
    seal = json.loads((root / 'probe-dependencies.json').read_text())
    assert hashlib.sha256(HELPER_PATH.read_bytes()).hexdigest() == seal[HELPER_NAME], 'Frozen helper changed'
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == seal['upgrade-probe.py'], 'Frozen probe changed'


def rejected_input_name_upgrade(env, case, root):
    """Exercise the actual candidate pre-migration on this saved fixture only.

    The extra language lives under an outer SQL savepoint and is rolled back.
    An actual customer translation is never removed to make an upgrade pass.
    """
    import runpy
    path = root / 'candidate-addons/step_payroll_oca_api/translation_storage.py'
    candidate = runpy.run_path(str(path))
    initial = raw_rows(env)
    env.cr.execute('SAVEPOINT step_private_name_language')
    try:
        env.cr.execute("UPDATE hr_payslip_input_type SET name=jsonb_set(name,'{es_CL}',to_jsonb(%s::text)) WHERE id=%s",
                       ('Private extra-language upgrade witness', case.input_type.id))
        assert env.cr.rowcount == 1
        before = raw_rows(env)
        try:
            candidate['migrate_original_translation_storage'](env.cr)
        except candidate['TranslationStorageError'] as error:
            assert str(error) == 'original-input-name-requires-one-literal-without-extra-languages'
        else:
            raise AssertionError('An extra input-name language was silently discarded')
        after = raw_rows(env)
        assert before == after, 'Rejected migration changed rows, IDs, schema or counters'
    finally:
        env.cr.execute('ROLLBACK TO SAVEPOINT step_private_name_language')
        env.cr.execute('RELEASE SAVEPOINT step_private_name_language')
    assert raw_rows(env) == initial, 'Private language fixture rollback was incomplete'
    write_private(root / 'input-name-rejected-upgrade.json', {
        'candidate_helper_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'private_fixture_id': case.input_type.id, 'synthetic_fixture_only': True,
        'actual_candidate_migration': True, 'extra_language_rejected': True,
        'rejection_code': 'original-input-name-requires-one-literal-without-extra-languages',
        'before_sha256': digest(before), 'after_sha256': digest(after),
        'rows_and_schema_unchanged': True, 'fixture_language_rolled_back': True,
        'writes_to_source': False, 'closed_payroll_recomputed': False})


def exercise(env, mode, directory):
    """Payload for the real Odoo shell, on the newly restored database only."""
    assert re.fullmatch(DATABASE_PATTERN, env.cr.dbname), 'Private upgrade clone required'
    root = Path(directory)
    verify_dependency(root)
    import threading
    threading.current_thread().testing = True
    from odoo import api, fields, Command
    from odoo.exceptions import UserError
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
        if UPGRADE_PROFILE == 'name-scalar':
            env['res.lang']._activate_lang('es_CL')
            case.rule.update_field_translations('note', {'es_CL': {
                'Nota histórica: acentos, 0 y espacios internos.': 'Private preserved Chilean note translation'}}, source_lang='en_US')
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
        unpaid = case.scope['hr.work.entry.type'].create({'name': 'Private admission unpaid day',
            'code': 'PRIVATE_ADMISSION_UNPAID', 'unpaid_structure_ids': [Command.link(case.structure.id)]})
        unpaid_day = case.scope['hr.payslip.worked_days'].create({'name': unpaid.name, 'code': unpaid.code,
            'payslip_id': slip.id, 'contract_id': case.contract.id, 'work_entry_type_id': unpaid.id,
            'number_of_days': 1, 'number_of_hours': 8})
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
        unpaid_values = {'amount': unpaid_day.amount, 'is_paid': unpaid_day.is_paid}
        assert day_values['is_paid'] and day_values['amount'] > 0
        assert unpaid_values == {'amount': 0, 'is_paid': False}, 'Existing unpaid relation is not effective'
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
        if UPGRADE_PROFILE == 'name-scalar':
            rejected_input_name_upgrade(env, case, root)
        rows = raw_rows(env)
        selected = next(row for row in rows['hr_payslip'] if row['id'] == slip.id)
        assert selected['paid'] and selected['step_history_locked'], 'History must be locked by the real closing flow'
        assert all(selected[name] == value for name, value in amounts.items()), 'Closing changed authentic draft amounts'
        stored_day = next(row for row in rows['hr_payslip_worked_days'] if row['id'] == day.id)
        assert all(stored_day[name] == value for name, value in day_values.items())
        stored_unpaid = next(row for row in rows['hr_payslip_worked_days'] if row['id'] == unpaid_day.id)
        assert all(stored_unpaid[name] == value for name, value in unpaid_values.items())
        assert all(rows['relations'][name] for name in RELATIONS), 'Seed must exercise all three original M2M stores'
        stored_rule = next(row for row in rows['hr_salary_rule'] if row['id'] == case.rule.id)
        assert isinstance(stored_rule['note'], dict) and stored_rule['note'].get('en_US')
        assert stored_rule['analytic_account_id'] == {str(case.company.id): analytic.id}, 'Original company property not seeded'
        entry = next(row for row in rows['account_move'] if row['id'] == selected['move_id'])
        lines = [row for row in rows['account_move_line'] if row['move_id'] == entry['id']]
        assert entry['state'] == 'posted' and len(lines) >= 2 and sum(row['debit'] for row in lines) > 0
        assert abs(sum(row['debit'] - row['credit'] for row in lines)) < 0.00001, 'Actual entry does not balance'
        historical = [row for row in rows['hr_payslip_line'] if row['slip_id'] == slip.id and row['salary_rule_id'] == case.rule.id]
        assert historical and all(isinstance(row['note'], str) and row['note'] and row['analytic_account_id'] == analytic.id for row in historical), 'Legacy history fixture lacks scalar properties'
        columns = {(row['table'], row['field']): row['data_type'] for row in rows['property_columns']}
        assert columns == {('hr_salary_rule', 'note'): 'jsonb', ('hr_salary_rule', 'analytic_account_id'): 'jsonb',
                           ('hr_payslip_line', 'note'): 'text', ('hr_payslip_line', 'analytic_account_id'): 'integer'}
        seed = {'synthetic_fixture_only': True, 'real_oca_engine': True, 'normal_actor': True,
            'actor': case.scope.uid, 'company': case.company.id, 'contract': case.contract.id,
            'rule': case.rule.id, 'null_rules': [gross.id, net.id], 'analytic': analytic.id,
            'slip': slip.id, 'structure': case.structure.id, 'day': day.id, 'unpaid_day': unpaid_day.id,
            'unpaid_type': unpaid.id, 'unpaid_day_values': unpaid_values, 'move': entry['id'], 'draft_amounts': amounts,
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
        scope = api.Environment(env.cr, seed['actor'], dict(env.context, allowed_company_ids=[seed['company']], lang='en_US'), su=False)
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
        assert len(pin['files']) == 52 and digest(pin['files']) == PROVIDER_SOURCE_FILES_SHA256
        for prefix in ('legacy', 'candidate'):
            derivation_bytes = (root / (prefix + '-provider-derivation.json')).read_bytes()
            assert hashlib.sha256(derivation_bytes).hexdigest() == xml_audit[prefix + '_provider_derivation_sha256']
            derivation = json.loads(derivation_bytes)
            assert derivation['license'] == 'AGPL-3' and derivation['source_files'] == pin['files']
            assert derivation['builder_sha256'] == xml_audit[prefix + '_builder_sha256'] == PROVIDER_BUILDER_SHA256
        for phase in ('before', 'after'):
            clock_bytes = (root / ('upgrade-sql-clock-' + phase + '.json')).read_bytes()
            assert hashlib.sha256(clock_bytes).hexdigest() == xml_audit['sql_clock_' + phase + '_sha256']
            assert json.loads(clock_bytes)['utc'] == xml_audit['sql_utc_' + phase]
        proof = verify_rows(seed['raw_rows'], before_read, xml_audit)
        # The real historical read API is required to use stored values. No
        # current wage/amount getter and no compute_sheet invocation occurs.
        slip = scope['hr.payslip'].browse(seed['slip'])
        if UPGRADE_PROFILE == 'saved-inputs':
            try:
                slip._step_check_saved_input_values()
            except UserError:
                proof['closed_saved_input_admission_refused'] = True
            else:
                raise AssertionError('Closed stored payroll was admitted as mutable saved inputs')
        values = slip._get_line_values(['BASIC', 'GROSS', 'NET'])
        expected = {row['code']: row['total'] for row in seed['raw_rows']['hr_payslip_line'] if row['slip_id'] == seed['slip']}
        for code in ('BASIC', 'GROSS', 'NET'):
            assert values[code][slip.id]['total'] == expected[code], 'Historical API did not return stored totals'
        structure = scope['hr.payroll.structure'].browse(seed['structure'])
        assert structure._step_check_original_required_contract() is True
        relation = structure._fields['unpaid_work_entry_type_ids']
        assert (relation.relation, relation.column1, relation.column2) == (
            'hr_payroll_structure_hr_work_entry_type_rel', 'hr_payroll_structure_id', 'hr_work_entry_type_id')
        assert set(structure.unpaid_work_entry_type_ids.ids) == {seed['unpaid_type']}, 'Original unpaid inverse lost its actual members'
        # Explicit calls exercise frozen-cache protection with today's changed
        # contract wage. No salary formula or line calculation is re-executed.
        slip._compute_provider_totals()
        scope['hr.payslip.worked_days'].browse([seed['day'], seed['unpaid_day']])._compute_payment()
        refused = False
        try:
            slip.compute_sheet()
        except UserError as error:
            assert str(error) in {'Closed payroll history cannot be recalculated.',
                'Validated or paid payroll cannot be recalculated.',
                'Closed payroll history cannot be changed or removed. Create a correction instead.'}, 'Recalculation failed for a reason other than the closed-history guard'
            refused = True
        assert refused, 'Closed payroll recomputation was not refused'
        env.flush_all()
        after_read = raw_rows(env)
        assert before_read == after_read, 'Historical read mutated stored payroll'
        write_private(root / 'rows-after.json', after_read)
        write_private(root / 'verified.json', dict(proof, actual_upgrade=True, normal_actor=True,
            real_oca_engine=True, historical_read_unchanged=True, closed_payroll_recomputed=False,
            synthetic_fixture_only=True, synthetic_paid_marker=True, payment_workflow_certified=False,
            synthetic_paid_marker_witness_sha256=seed['synthetic_paid_marker_witness_sha256'],
            synthetic_paid_marker_original_sql_value=seed['synthetic_paid_marker_original_sql_value'],
            current_wage_changed_after_closure=True, original_required_admission_normal_actor=True,
            original_unpaid_inverse_preserved=True, frozen_compute_preserved=True, closed_compute_refused=True,
            customer_payroll_certified=False, engine_conversion=False))
        env.cr.rollback()
    else:
        raise AssertionError('Unsupported private rehearsal payload')


def main():
    import configparser
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'candidate', 'runtime', 'oca'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--profile', choices=('admission', 'period', 'name-scalar', 'saved-inputs'), default='admission')
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    configure_profile(args.profile)
    assert hasattr(os, 'geteuid') and os.geteuid() == 0, 'Linux root execution required'
    import fcntl
    import pwd
    assert re.fullmatch(DATABASE_PATTERN, args.database)
    os.umask(0o077)
    root, source_root, candidate = args.root.resolve(), (args.source_root or SOURCE_ROOT).resolve(), args.candidate.resolve()
    assert Path('/opt/steps-validation') in root.parents and not root.exists()
    assert source_root == SOURCE_ROOT and Path('/opt/steps-validation') in candidate.parents
    assert source_root not in root.parents, 'Never place rehearsal artifacts inside accepted F'
    assert root != candidate and root not in candidate.parents and candidate not in root.parents
    acceptance_path = source_root / 'community/passed.json'
    accepted = json.loads(acceptance_path.read_text())
    assert accepted['database'] == SOURCE_DB and accepted['mode'] == 'community' and accepted['counts']['enterprise'] == 0
    assert accepted['counts']['installed'] == SOURCE_INSTALLED_COUNT
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
        if module == 'step_payroll_oca_api':
            assert any((candidate / module / 'migrations' / versions[1]).glob('pre-*.py')), 'Required API admission pre-migration is not wired'
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
    dependency = root / HELPER_NAME
    with dependency.open('xb') as stream:
        stream.write(HELPER_PATH.read_bytes())
    write_private(root / 'probe-dependencies.json', {
        HELPER_NAME: hashlib.sha256(dependency.read_bytes()).hexdigest(),
        'upgrade-probe.py': hashlib.sha256(probe_copy.read_bytes()).hexdigest()})
    with open('/run/lock/steps-environments.lock', 'a') as lease:
        print('PAYROLL_ADMISSION_UPGRADE_WAITING_FOR_SHARED_LEASE', flush=True)
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
        assert len(source_pin['files']) == 52 and digest(source_pin['files']) == PROVIDER_SOURCE_FILES_SHA256
        assert manifest(legacy / 'l10n_cl_simpledigital_payroll')['license'] == 'AGPL-3'
        for phase in ('legacy', 'candidate'):
            assert set(files['l10n_cl_simpledigital_payroll'][phase]) == set(source_pin['files'])
            assert files['l10n_cl_simpledigital_payroll'][phase][CONFIG_XML] == DERIVED_CONFIG_XML_SHA256
        derivations = {}
        for phase, package in (('legacy', source_root), ('candidate', candidate.parent)):
            derivation_bytes = (package / 'provider-derivation.json').read_bytes()
            assert hashlib.sha256(derivation_bytes).hexdigest() == PROVIDER_DERIVATION_SHA256
            derivation = json.loads(derivation_bytes)
            assert derivation['license'] == 'AGPL-3' and derivation['source_files'] == source_pin['files']
            builder = package / 'addons/tools/community/build_simpledigital_candidate.py'
            assert hashlib.sha256(builder.read_bytes()).hexdigest() == derivation['builder_sha256'] == PROVIDER_BUILDER_SHA256
            assert CONFIG_XML in derivation['transformed_files'] and not derivation['identity_conversion_accepted']
            derivations[phase] = derivation
            with (root / (phase + '-provider-derivation.json')).open('xb') as stream:
                stream.write(derivation_bytes)
        assert derivations['legacy'] == derivations['candidate']
        with (root / 'xml-config-source-pin.json').open('xb') as stream:
            stream.write(pin_bytes)
        for path in (root, *root.rglob('*')):
            if not path.is_symlink():
                os.chown(path, identity.pw_uid, identity.pw_gid)
                if path.is_file():
                    os.chmod(path, 0o600)
        def execute(label, overlay, flags=(), payload=None):
            command = offline_command(args.runtime, overlay, data, args.database,
                root / (label + '.log'), flags=flags, shell=payload is not None)
            with (root / (label + '-bootstrap.log')).open('x') as log:
                status = subprocess.run(command, input=payload, text=True, stdout=log, stderr=subprocess.STDOUT)
            logfile = root / (label + '.log')
            log = logfile.read_text(errors='replace') if logfile.exists() else ''
            assert status.returncode == 0 and not re.search(r' (ERROR|CRITICAL) ', log), 'Blocked; inspect private log: ' + str(logfile)
            capacity()
        probe = str(probe_copy)
        seed = "import sys,threading,runpy; threading.current_thread().testing=True; sys.path.insert(0," + repr(str(root)) + "); probe=runpy.run_path(" + repr(probe) + "); probe['configure_profile'](" + repr(UPGRADE_PROFILE) + "); probe[\"exercise\"](env,\"seed\"," + repr(str(root)) + ')'
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
            'approved_derived_xml_sha256': DERIVED_CONFIG_XML_SHA256,
            'provider_source_file_count': len(source_pin['files']),
            'provider_source_files_sha256': digest(source_pin['files']),
            'legacy_builder_sha256': derivations['legacy']['builder_sha256'],
            'candidate_builder_sha256': derivations['candidate']['builder_sha256'],
            'legacy_provider_derivation_sha256': hashlib.sha256((root / 'legacy-provider-derivation.json').read_bytes()).hexdigest(),
            'candidate_provider_derivation_sha256': hashlib.sha256((root / 'candidate-provider-derivation.json').read_bytes()).hexdigest(),
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
        assert source_after == source_before, 'Accepted source F changed'
        assert (file_manifest(source_store) if source_store.exists() else {}) == source_store_before, 'Source F filestore changed'
        assert all(file_manifest(legacy / module) == value['legacy'] and file_manifest(upgraded / module) == value['candidate']
                   for module, value in files.items()), 'Frozen upgrade code changed'
        proof = json.loads((root / 'verified.json').read_text())
        proof.update(upgrade_profile=UPGRADE_PROFILE, source_database=SOURCE_DB, database=args.database, original_versions={m: v[0] for m, v in VERSIONS.items()},
            target_versions=actual, source_acceptance_sha256=hashlib.sha256(acceptance_path.read_bytes()).hexdigest(),
            source_snapshot_sha256=digest(source_after), source_unchanged=True, source_filestore_unchanged=True,
            backup_decoded=True, backup_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),
            package_files_sha256=digest(files), writes_to_source=False, module_states_rewritten=False,
            source_consumer_files_sha256=digest(consumer_fingerprints),
            seed_sha256=hashlib.sha256((root / 'seed.json').read_bytes()).hexdigest(),
            rows_after_sha256=hashlib.sha256((root / 'rows-after.json').read_bytes()).hexdigest(),
            xml_config_upgrade_audit_sha256=hashlib.sha256((root / 'xml-config-upgrade-audit.json').read_bytes()).hexdigest(),
            official_community_revision=OFFICIAL_PIN, oca_revision=OCA_PIN,
            tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            helper_sha256=hashlib.sha256(dependency.read_bytes()).hexdigest(),
            probe_dependencies_sha256=hashlib.sha256((root / 'probe-dependencies.json').read_bytes()).hexdigest(),
            runtime_network_isolated=True, postgres_unix_socket=True, full_community_conversion=False)
        write_private(root / 'passed.json', proof)
        print(json.dumps({key: proof[key] for key in ('actual_upgrade', 'raw_rows_preserved', 'historical_read_unchanged',
            'source_unchanged', 'source_filestore_unchanged', 'backup_decoded', 'writes_to_source', 'full_community_conversion')}))


if __name__ == '__main__':
    main()
