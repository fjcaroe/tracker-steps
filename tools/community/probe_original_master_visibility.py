"""Observe ORIGINAL native master ID visibility under an existing normal actor.

Run only against a fresh private native Cerro control and an already loaded
registry. The observer opens an official read-only connection, reads no payroll
history/formula/amount fields, grants nothing and does not derive a target rule.
"""
import hashlib
import json
import os
from pathlib import Path
import re


CAPSULE_SHA256 = '14b18ced97032ec27c306ed4c71c46f0c3d56e324d0eace4f0c8f2c86544e140'
SPECS = {
    'hr_payroll_structure': ('hr.payroll.structure', ('id', 'country_id', 'type_id', 'active')),
    'hr_payroll_structure_type': ('hr.payroll.structure.type', ('id', 'country_id')),
    'hr_payslip_input_type': ('hr.payslip.input.type', ('id', 'country_id', 'active')),
    'hr_salary_rule': ('hr.salary.rule', ('id', 'struct_id', 'category_id', 'active')),
    'hr_salary_rule_category': ('hr.salary.rule.category', ('id', 'parent_id')),
}


def require(value, code):
    if not value:
        raise ValueError(code)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def identifier(value):
    require(re.fullmatch(r'[a-z_][a-z0-9_]*', value) is not None, 'invalid-static-identifier')
    return '"' + value + '"'


def expected_projection(capsule):
    result = {}
    for table, (model, columns) in SPECS.items():
        entry = capsule['tables'][table]
        rows = [json.loads(raw) for raw in entry['rows_json']]
        require(entry['model'] == model and entry['row_count'] == len(rows)
            and len({row['id'] for row in rows}) == len(rows), 'original-capsule-identity-invalid')
        require(all(all(column in row for column in columns) for row in rows), 'original-projection-column-missing')
        result[table] = [{column: row[column] for column in columns} for row in sorted(rows, key=lambda row: row['id'])]
    require(sum(len(rows) for rows in result.values()) == 120, 'exact-original120-required')
    return result


def physical_projection(cr):
    result = {}
    for table, (model, columns) in SPECS.items():
        cr.execute('SELECT ' + ','.join(identifier(name) for name in columns) + ' FROM ' + identifier(table) + ' ORDER BY id')
        result[table] = [dict(zip(columns, row)) for row in cr.fetchall()]
    return result


def observe_model(model, ids, *, access_error):
    require(not model.env.su, 'normal-actor-required')
    try:
        searched = sorted(model.search([('id', 'in', ids)], order='id').ids)
        search_denied = False
    except access_error:
        searched, search_denied = [], True
    allowed, denied = [], []
    for ident in ids:
        try:
            actual = model.browse(ident).read(['id'])
        except access_error:
            denied.append(ident)
        else:
            require(actual == [{'id': ident}], 'source-read-returned-extra-fields-or-another-id')
            allowed.append(ident)
    require(searched == sorted(allowed) and sorted(allowed + denied) == sorted(ids), 'source-search-read-visibility-inconsistent')
    return {'capsule_ids': list(ids), 'search_ids': searched, 'allowed_ids': allowed, 'denied_ids': denied,
        'search_model_access_denied': search_denied, 'read_fields': ['id'], 'read_denial_kind': 'AccessError',
        'search_and_per_record_read_agree': True, 'superuser': False}


def policy_snapshot(cr):
    models = [model for model, columns in SPECS.values()] + ['hr.payslip']
    result = {}
    for table, where in (
        ('ir_model_access', 'WHERE t.model_id IN (SELECT id FROM ir_model WHERE model=ANY(%s))'),
        ('ir_rule', 'WHERE t.model_id IN (SELECT id FROM ir_model WHERE model=ANY(%s))'),
        ('rule_group_rel', 'WHERE t.rule_group_id IN (SELECT r.id FROM ir_rule r JOIN ir_model m ON m.id=r.model_id WHERE m.model=ANY(%s))'),
        ('ir_model_fields_group_rel', 'WHERE t.field_id IN (SELECT f.id FROM ir_model_fields f WHERE f.model=ANY(%s))'),
        ('res_groups', ''), ('res_groups_users_rel', ''), ('res_groups_implied_rel', ''), ('res_company_users_rel', ''),
    ):
        cr.execute("SELECT count(*),encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex') FROM "
            + identifier(table) + ' t ' + where, (models,) if where else ())
        count, digest = cr.fetchone(); result[table] = {'rows': count, 'sha256': digest}
    return result


def counter_snapshot(cr):
    cr.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' "
        "AND c.relkind='S' AND c.relname ~ '^ir_sequence_[0-9]+(_[0-9]+)?$' ORDER BY c.relname")
    names = [row[0] for row in cr.fetchall()]
    result = {}
    for name in names:
        cr.execute('SELECT last_value,log_cnt,is_called FROM ' + identifier(name))
        result[name] = list(cr.fetchone())
    require(len(result) >= 140, 'original-business-counter-inventory-incomplete')
    return result


def run(env, capsule_path, capsule_sha256, *, actor_uid=7, company_ids=(1, 2, 3, 4), active_company_id=2, output):
    from odoo import api, sql_db
    from odoo.exceptions import AccessError

    database = env.cr.dbname
    require(re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_REFERENCE_[A-Za-z0-9_]+', database),
        'fresh-private-original-native-control-required')
    output = Path(output).resolve()
    require(output.is_relative_to(Path('/opt/steps-validation')) and output.parent.is_dir() and not output.exists(),
        'new-private-source-proof-required')
    raw = Path(capsule_path).read_bytes()
    require(capsule_sha256 == CAPSULE_SHA256 == sha(raw), 'original-source-capsule-seal-differs')
    capsule = json.loads(raw); expected = expected_projection(capsule)
    require(type(actor_uid) is int and actor_uid > 0 and len(set(company_ids)) == len(company_ids)
        and active_company_id in company_ids, 'explicit-existing-actor-and-company-context-required')
    mro = [klass.__module__ + '.' + klass.__name__ for klass in type(env['hr.payslip']).__mro__]
    require(env['hr.payslip']._table == 'hr_payslip' and any(name.startswith('odoo.addons.hr_payroll.') for name in mro)
        and not any(name.startswith('odoo.addons.payroll.') for name in mro), 'actual-original-native-engine-required')
    # Use the already loaded registry; no Registry.new, upgrade or native code
    # override. This cursor remains genuinely read-only for every ORM read.
    with sql_db.db_connect(database, readonly=True).cursor() as cr:
        cr.execute('SELECT current_database(),current_setting(\'transaction_read_only\'),current_setting(\'transaction_isolation\'),pg_is_in_recovery()')
        transaction = cr.fetchone()
        require(transaction == (database, 'on', 'repeatable read', False) and cr.readonly is True,
            'real-primary-readonly-repeatable-read-cursor-required')
        cr.execute("SELECT name,latest_version,license,state FROM ir_module_module WHERE state='installed' ORDER BY name")
        modules = [dict(zip(('name', 'version', 'license', 'state'), row)) for row in cr.fetchall()]
        require(len(modules) == 381 and sum(row['license'] == 'OEEL-1' for row in modules) == 140,
            'untouched-source381-native140-required')
        require(any(row['name'] == 'hr_payroll' and row['license'] == 'OEEL-1' for row in modules)
            and not any(row['name'] in ('payroll', 'payroll_account') for row in modules), 'native-provider-scope-differs')
        cr.execute("SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")
        require(cr.fetchone() == (0,), 'source-has-pending-module-operation')
        cr.execute("SELECT id FROM ir_model WHERE model='hr.payslip'")
        model_ids = [row[0] for row in cr.fetchall()]
        require(model_ids == [600], 'original-payslip-model-identity600-required')
        reports = sorted({json.loads(row)['report_id'] for row in capsule['tables']['hr_payroll_structure']['rows_json']
            if json.loads(row).get('report_id') is not None})
        cr.execute('SELECT id,model FROM ir_act_report_xml WHERE id=ANY(%s) ORDER BY id', (reports,))
        report_rows = [list(row) for row in cr.fetchall()]
        require(report_rows == [[ident, 'hr.payslip'] for ident in reports] and 462 in reports, 'original-payslip-report462-required')
        before = physical_projection(cr); require(before == expected, 'source-native120-physical-projection-differs')
        policy_before, counters_before = policy_snapshot(cr), counter_snapshot(cr)
        context = dict(env.context, allowed_company_ids=[active_company_id] + [value for value in company_ids if value != active_company_id],
            active_test=False, lang='en_US')
        actor_env = api.Environment(cr, actor_uid, context, su=False)
        require(not actor_env.su and actor_env.user.id == actor_uid and actor_env.company.id == active_company_id,
            'actual-normal-actor-context-required')
        memberships = sorted(actor_env.user.company_ids.ids)
        require(set(company_ids) <= set(memberships), 'source-company-membership-is-not-authorized')
        require(actor_env.user.has_group('hr_payroll.group_hr_payroll_manager')
            and not actor_env.user.has_group('base.group_system'), 'existing-non-system-native-manager-required')
        observations = {}
        for table, (model, columns) in SPECS.items():
            require(actor_env[model]._table == table, 'original-model-table-binding-differs')
            observations[model] = observe_model(actor_env[model], [row['id'] for row in expected[table]], access_error=AccessError)
        after = physical_projection(cr)
        policy_after, counters_after = policy_snapshot(cr), counter_snapshot(cr)
        require(before == after and policy_before == policy_after and counters_before == counters_after,
            'original-master-policy-or-counter-changed-during-observation')
        proof = {'schema': 1, 'profile': 'source-native-original-master-id-visibility', 'database': database,
            'probe_sha256': sha(Path(__file__).read_bytes()), 'capsule_sha256': capsule_sha256,
            'transaction': {'read_only': True, 'odoo_cursor_readonly': True, 'isolation': 'repeatable read', 'local_primary': True},
            'engine': {'mro': mro, 'installed': len(modules), 'enterprise': 140, 'oca_installed': False,
                'payslip_model_id': 600, 'report_rows': report_rows, 'module_metadata_sha256': sha(encode(modules))},
            'actor': {'uid': actor_uid, 'allowed_company_ids': sorted(company_ids), 'active_company_id': active_company_id,
                'original_company_memberships': memberships, 'superuser': False, 'system_group_member': False,
                'original_native_payroll_manager': True, 'users_created': False, 'permissions_granted': False},
            'models': observations, 'original_sql_projection': before, 'original_sql_projection_sha256': sha(encode(before)),
            'original_projection_exact_after': True, 'policy_before': policy_before, 'policy_after': policy_after,
            'business_counters_before': counters_before, 'business_counters_after': counters_after,
            'normal_actor_source_visibility_proven': True, 'master_orm_fields_read': ['id'],
            'actor_context_fields_read': ['company_ids', 'groups_id'], 'security_related_metadata_read': True, 'active_test': False,
            'total_original_masters': sum(len(row['capsule_ids']) for row in observations.values()),
            'allowed_master_ids': sum(len(row['allowed_ids']) for row in observations.values()),
            'denied_master_ids': sum(len(row['denied_ids']) for row in observations.values()),
            'source_model_code_overridden': False, 'source_country_domain_evaluated_locally': False,
            'historical_payroll_read': False, 'salary_rules_evaluated': False, 'salary_amounts_read': False,
            'formula_bodies_read_from_database': False, 'database_writes': False, 'financial_certified': False,
            'identity_conversion': False, 'all_products_operational': False, 'deadline_resolved': False}
    body = json.dumps(proof, indent=2, ensure_ascii=False).encode()
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(body)
    return proof
