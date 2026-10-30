"""One atomic SQL-only capture of the user-approved real SyS payroll reference.

Private financial evidence only. No ORM, formula evaluation, source writes or
historical recomputation. XML IDs prove logical references, never equal money,
historical master versions or permission to transplant one product's policy.
"""
import argparse
import ast
import configparser
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


CERRO_CAPSULE_SHA256 = '14b18ced97032ec27c306ed4c71c46f0c3d56e324d0eace4f0c8f2c86544e140'
CONFIG_TABLES = ('hr_payroll_structure', 'hr_payroll_structure_type', 'hr_salary_rule',
    'hr_salary_rule_category', 'hr_payslip_input_type')
CONFIG_RELATIONS = ('hr_payroll_structure_hr_payslip_input_type_rel',)
NUMERIC_RULE_VALUES = ('amount_fix', 'amount_percentage', 'condition_range_min', 'condition_range_max')
PAYROLL_TABLES = ('hr_payslip', 'hr_payslip_line', 'hr_payslip_worked_days', 'hr_payslip_input',
    'hr_work_entry', 'hr_contract')
EXPRESSION_FIELDS = ('amount_python_compute', 'condition_python', 'condition_range',
    'quantity', 'amount_percentage_base')
RULE_VALUES = ('code', 'active', 'sequence', 'amount_select', 'condition_select',
    'amount_fix', 'amount_percentage', 'condition_range_min', 'condition_range_max',
    'not_computed_in_net', 'split_move_lines', 'appears_on_payslip')
RULE_REFERENCES = {'category_id': 'hr.salary.rule.category', 'struct_id': 'hr.payroll.structure',
    'condition_other_input_id': 'hr.payslip.input.type', 'amount_other_input_id': 'hr.payslip.input.type'}
MODELS = {'hr_payroll_structure': 'hr.payroll.structure', 'hr_payroll_structure_type': 'hr.payroll.structure.type',
    'hr_salary_rule': 'hr.salary.rule', 'hr_salary_rule_category': 'hr.salary.rule.category',
    'hr_payslip_input_type': 'hr.payslip.input.type'}


class CaptureError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise CaptureError(code)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def resolve_source(registry, config_loader):
    require(registry.get('instance') == 'odoo-new', 'canonical-instance-required')
    row = registry.get('environments', {}).get('sys', {})
    require(row.get('role') == 'production' and row.get('database') == 'SyS'
        and row.get('config') == '/etc/odoo18-sys.conf', 'canonical-sys-profile-required')
    config = config_loader(row['config'])
    require(config.get('db_name') == row['database'], 'runtime-database-registry-mismatch')
    # Do not return, log or serialize passwords or the complete options map.
    return row['database'], row['config'], tuple(Path(p.strip()) for p in config['addons_path'].split(','))


def provider_snapshot(roots, pin):
    provider = next((p / 'l10n_cl_simpledigital_payroll' for p in roots
        if (p / 'l10n_cl_simpledigital_payroll/__manifest__.py').is_file()), None)
    require(provider is not None, 'active-provider-source-missing')
    manifest = ast.literal_eval((provider / '__manifest__.py').read_text(encoding='utf-8-sig'))
    require(manifest.get('license') == pin['license'] == 'AGPL-3'
        and manifest.get('version') == pin['version'], 'provider-license-version-drift')
    hashes = {}
    for name, expected in pin['files'].items():
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts, 'provider-pin-path-invalid')
        path = provider / relative
        require(path.is_file() and not path.is_symlink(), 'provider-file-not-regular')
        hashes[name] = sha(path.read_bytes())
        require(hashes[name] == expected, 'provider-runtime-pin-drift')
    return {'path': str(provider), 'license': manifest['license'], 'version': manifest['version'], 'files': hashes}


def sql_capture(as_of):
    day = date.fromisoformat(as_of).isoformat()
    snapshots = []
    for table in CONFIG_TABLES + CONFIG_RELATIONS + PAYROLL_TABLES:
        snapshots.append("'%s',(SELECT jsonb_build_object('rows',count(*),'sha256',encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex')) FROM %s t)" % (table, table))
    expressions = ','.join("'%s',jsonb_build_object('is_null',to_jsonb(r)->'%s' IS NULL OR to_jsonb(r)->'%s'='null'::jsonb,'sha256',encode(sha256(convert_to(coalesce(to_jsonb(r)->>'%s',''),'UTF8')),'hex'))" % (field, field, field, field) for field in EXPRESSION_FIELDS)
    values = ','.join("'%s',to_jsonb(r)%s'%s'" % (field, '->>' if field in NUMERIC_RULE_VALUES else '->', field) for field in RULE_VALUES)
    references = ','.join("'%s',to_jsonb(r)->'%s'" % (field, field) for field in RULE_REFERENCES)
    tables = ','.join("'%s'" % name for name in CONFIG_TABLES + CONFIG_RELATIONS + PAYROLL_TABLES)
    models = ','.join("'%s'" % name for name in MODELS.values())
    return """BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='120s';
SET LOCAL lock_timeout='5s';
WITH closed AS MATERIALIZED (
 SELECT s.* FROM public.hr_payslip s
 WHERE s.state IN ('done','paid') AND s.date_to < date_trunc('month', DATE '%s')::date
), selected_contracts AS MATERIALIZED (SELECT DISTINCT contract_id FROM closed WHERE contract_id IS NOT NULL)
SELECT jsonb_build_object(
 'metadata',jsonb_build_object('database',current_database(),'transaction_read_only',current_setting('transaction_read_only'),
   'default_transaction_read_only',current_setting('default_transaction_read_only'),'isolation',current_setting('transaction_isolation'),
   'in_recovery',pg_is_in_recovery(),'snapshot',txid_current_snapshot()::text,'captured_at',transaction_timestamp(),
   'server_version_num',current_setting('server_version_num'),'as_of','%s'),
 'pending',(SELECT coalesce(jsonb_agg(jsonb_build_object('name',name,'state',state) ORDER BY name),'[]') FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')),
 'providers',(SELECT coalesce(jsonb_agg(jsonb_build_object('name',name,'license',license,'version',latest_version,'state',state) ORDER BY name),'[]') FROM ir_module_module WHERE name IN ('hr_payroll','hr_payroll_account','l10n_cl_simpledigital_payroll')),
 'schema',(SELECT coalesce(jsonb_object_agg(relname,cols),'{}') FROM (SELECT c.relname,jsonb_agg(jsonb_build_array(a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull) ORDER BY a.attnum) cols FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped WHERE n.nspname='public' AND c.relname IN (%s) GROUP BY c.relname) t),
 'field_metadata',(SELECT coalesce(jsonb_agg(jsonb_build_object('id',f.id,'model',f.model,'name',f.name,'ttype',to_jsonb(f)->'ttype','relation',to_jsonb(f)->'relation','store',to_jsonb(f)->'store','required',to_jsonb(f)->'required','readonly',to_jsonb(f)->'readonly','related',to_jsonb(f)->'related','translate',to_jsonb(f)->'translate','company_dependent',to_jsonb(f)->'company_dependent') ORDER BY f.id),'[]') FROM ir_model_fields f WHERE f.model IN (%s) OR f.model IN ('hr.payslip','hr.payslip.line','hr.payslip.input','hr.payslip.worked_days')),
 'snapshots',jsonb_build_object(%s),
 'policy',jsonb_build_object(
  'access',(SELECT jsonb_build_object('rows',count(*),'sha256',encode(sha256(convert_to(coalesce(string_agg(to_jsonb(a)::text,E'\\n' ORDER BY a.id),''),'UTF8')),'hex')) FROM ir_model_access a JOIN ir_model m ON m.id=a.model_id WHERE m.model IN (%s)),
  'rules',(SELECT jsonb_build_object('rows',count(*),'sha256',encode(sha256(convert_to(coalesce(string_agg(to_jsonb(r)::text,E'\\n' ORDER BY r.id),''),'UTF8')),'hex')) FROM ir_rule r JOIN ir_model m ON m.id=r.model_id WHERE m.model IN (%s))),
 'closed_population',(SELECT jsonb_build_object('all_closed',count(*),'previous_months',count(*) FILTER(WHERE date_to < date_trunc('month', DATE '%s')::date)) FROM hr_payslip WHERE state IN ('done','paid')),
 'headers',(SELECT coalesce(jsonb_agg(jsonb_build_object('id',s.id,'state',s.state,'date_from',s.date_from,'date_to',s.date_to,'company_id',s.company_id,'contract_id',s.contract_id,'struct_id',s.struct_id,'credit_note',to_jsonb(s)->'credit_note','run_id',to_jsonb(s)->'payslip_run_id','number_sha256',encode(sha256(convert_to(coalesce(to_jsonb(s)->>'number',''),'UTF8')),'hex'),'write_date',s.write_date) ORDER BY s.id),'[]') FROM closed s),
 'lines',(SELECT coalesce(jsonb_agg(jsonb_build_object('id',l.id,'slip_id',l.slip_id,'salary_rule_id',l.salary_rule_id,'code',l.code,'amount',l.amount::text,'quantity',l.quantity::text,'rate',l.rate::text,'total',l.total::text,'write_date',l.write_date) ORDER BY l.id),'[]') FROM hr_payslip_line l JOIN closed s ON s.id=l.slip_id),
 'worked_days',(SELECT coalesce(jsonb_agg(jsonb_build_object('id',w.id,'payslip_id',w.payslip_id,'type_id',w.work_entry_type_id,'days',w.number_of_days::text,'hours',w.number_of_hours::text,'amount',w.amount::text,'is_paid',to_jsonb(w)->'is_paid','stored_code',to_jsonb(w)->'code','current_type_code',t.code,'write_date',w.write_date) ORDER BY w.id),'[]') FROM hr_payslip_worked_days w JOIN closed s ON s.id=w.payslip_id LEFT JOIN hr_work_entry_type t ON t.id=w.work_entry_type_id),
 'inputs',(SELECT coalesce(jsonb_agg(jsonb_build_object('id',i.id,'payslip_id',i.payslip_id,'type_id',i.input_type_id,'amount',i.amount::text,'current_type_code',t.code,'write_date',i.write_date) ORDER BY i.id),'[]') FROM hr_payslip_input i JOIN closed s ON s.id=i.payslip_id LEFT JOIN hr_payslip_input_type t ON t.id=i.input_type_id),
 'work_entries',(SELECT coalesce(jsonb_agg(jsonb_build_object('id',e.id,'contract_id',e.contract_id,'type_id',e.work_entry_type_id,'date_start',e.date_start,'date_stop',e.date_stop,'state',e.state,'duration',to_jsonb(e)->>'duration','write_date',e.write_date) ORDER BY e.id),'[]') FROM hr_work_entry e JOIN selected_contracts c ON c.contract_id=e.contract_id),
 'contract_provenance',(SELECT coalesce(jsonb_agg(jsonb_build_object('id',c.id,'write_date',c.write_date,'resource_calendar_id',to_jsonb(c)->'resource_calendar_id','current_values_are_historical',false) ORDER BY c.id),'[]') FROM hr_contract c JOIN selected_contracts x ON x.contract_id=c.id),
 'rules',(SELECT coalesce(jsonb_agg(jsonb_build_object('id',r.id,'write_date',r.write_date,'values',jsonb_build_object(%s),'references',jsonb_build_object(%s),'expressions',jsonb_build_object(%s),'row_sha256',encode(sha256(convert_to(to_jsonb(r)::text,'UTF8')),'hex')) ORDER BY r.id),'[]') FROM hr_salary_rule r),
 'aliases',(SELECT coalesce(jsonb_agg(jsonb_build_object('id',d.id,'module',d.module,'name',d.name,'model',d.model,'res_id',d.res_id,'noupdate',d.noupdate) ORDER BY d.id),'[]') FROM ir_model_data d WHERE d.model IN (%s)),
 'structure_inputs',(SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]') FROM hr_payroll_structure_hr_payslip_input_type_rel t),
 'category_graph',(SELECT coalesce(jsonb_agg(jsonb_build_object('id',id,'code',code,'parent_id',parent_id) ORDER BY id),'[]') FROM hr_salary_rule_category),
 'structure_graph',(SELECT coalesce(jsonb_agg(jsonb_build_object('id',s.id,'country_id',to_jsonb(s)->'country_id','type_id',to_jsonb(s)->'type_id','active',to_jsonb(s)->'active','parent_id',to_jsonb(s)->'parent_id','journal_id',to_jsonb(s)->'journal_id','report_id',to_jsonb(s)->'report_id') ORDER BY s.id),'[]') FROM hr_payroll_structure s),
 'configuration_keys',jsonb_build_object(%s)
);
ROLLBACK;
""" % (day, day, tables, models, ','.join(snapshots), models, models, day, values, references, expressions, models,
 ','.join("'%s',(SELECT coalesce(jsonb_agg(id ORDER BY id),'[]') FROM %s)" % (model, table) for table, model in MODELS.items()))


def readonly_capture(statement):
    # Peer authentication over the existing local Unix socket. No password is
    # loaded or passed to a process; no inherited PG service/connection options.
    command = ['sudo', '-u', 'postgres', 'env', '-i', 'PATH=/usr/bin:/bin', 'HOME=/var/lib/postgresql',
        'PGHOST=/var/run/postgresql', 'PGOPTIONS=-c default_transaction_read_only=on',
        'PGPASSFILE=/opt/steps-validation/no-such-readonly-passfile',
        'psql', '-XAtq', '--no-password', '-v', 'ON_ERROR_STOP=1', '-d', 'SyS']
    result = subprocess.run(command, input=statement, text=True, encoding='utf-8', capture_output=True)
    require(result.returncode == 0, 'atomic-readonly-capture-failed-raw-diagnostics-withheld')
    lines = [line for line in result.stdout.splitlines() if line]
    require(len(lines) == 1, 'atomic-single-payload-required')
    return json.loads(lines[0])


def identities(rows, model, ident):
    return {(r['module'], r['name']) for r in rows if r['model'] == model and r['res_id'] == ident
        and r['module'] != 'step_simpledigital_oca_security'}


def expression(value):
    return {'is_null': value is None, 'sha256': sha(('' if value is None else str(value)).encode())}


def compare_rules(capsule, payload):
    table = capsule['tables']['hr_salary_rule']
    rules = [json.loads(row, parse_float=Decimal) for row in table['rows_json']]
    require(table['row_count'] == len(rules) == 71 and len({r['id'] for r in rules}) == 71,
        'exact-original-71-rule-cohort-required')
    aliases, original_aliases = payload['aliases'], capsule['xmlids']
    current = {r['id']: r for r in payload['rules']}
    coverage = {}
    for row in payload['lines']:
        coverage.setdefault(row['salary_rule_id'], []).append(row)
    matrix = []
    for row in rules:
        names = identities(original_aliases, 'hr.salary.rule', row['id'])
        candidate_ids = {a['res_id'] for a in aliases if a['model'] == 'hr.salary.rule'
            and (a['module'], a['name']) in names}
        blockers, differences = [], []
        if len(candidate_ids) != 1:
            blockers.append('ORIGINAL_RULE_IDENTITY_UNPROVEN' if not candidate_ids else 'ORIGINAL_RULE_IDENTITY_AMBIGUOUS')
        other = current.get(next(iter(candidate_ids))) if len(candidate_ids) == 1 else None
        if other is None:
            if candidate_ids: blockers.append('RULE_REFERENCE_DANGLING')
        else:
            for name in RULE_VALUES:
                left, right = row.get(name), other['values'].get(name)
                if name in NUMERIC_RULE_VALUES:
                    left = None if left is None else Decimal(str(left))
                    right = None if right is None else Decimal(str(right))
                if left != right: differences.append(name)
            for name in EXPRESSION_FIELDS:
                if expression(row.get(name)) != other['expressions'].get(name): differences.append(name + '_sha256')
            for name, model in RULE_REFERENCES.items():
                original, target = row.get(name), other['references'].get(name)
                if original is None and target is None: continue
                left = identities(original_aliases, model, original)
                right = identities(aliases, model, target)
                if not left or not right or not left.intersection(right): differences.append(name + '_identity')
            if differences: blockers.append('CURRENT_CONFIGURATION_DIFFERS')
        applied = coverage.get(other['id'], []) if other else []
        if not applied: blockers.append('NO_STORED_RULE_COVERAGE')
        # Current hashes and write dates do not prove the rule used originally.
        blockers.append('HISTORICAL_CONFIGURATION_TIMELINE_UNPROVEN')
        matrix.append({'cerro_rule_id': row['id'], 'sys_rule_id': other['id'] if other else None,
            'binding': 'same_original_xmlid' if other else None, 'current_differences': differences,
            'stored_line_ids': [r['id'] for r in applied], 'stored_slip_ids': sorted({r['slip_id'] for r in applied}),
            'blockers': blockers, 'financial_equivalence_certified': False})
    reverse = {}
    for row in matrix:
        if row['sys_rule_id'] is not None:
            reverse.setdefault(row['sys_rule_id'], []).append(row)
    for rows in reverse.values():
        if len(rows) > 1:
            for row in rows:
                row['blockers'].append('ORIGINAL_RULE_NAMESPACE_MERGED')
                row['binding'] = None
    return matrix


def validate_payload(payload, provider):
    meta = payload['metadata']
    require(meta['database'] == 'SyS' and meta['transaction_read_only'] == meta['default_transaction_read_only'] == 'on'
        and meta['isolation'] == 'repeatable read' and meta['in_recovery'] is False,
        'readonly-primary-repeatable-read-required')
    require(payload['pending'] == [], 'pending-module-operation-blocks-reference')
    providers = {row['name']: row for row in payload['providers']}
    require(set(providers) == {'hr_payroll', 'hr_payroll_account', 'l10n_cl_simpledigital_payroll'}, 'real-native-providers-required')
    require(all(row['state'] == 'installed' for row in providers.values())
        and all(providers[m]['license'] == 'OEEL-1' for m in ('hr_payroll', 'hr_payroll_account'))
        and providers['l10n_cl_simpledigital_payroll']['license'] == 'AGPL-3'
        and providers['l10n_cl_simpledigital_payroll']['version'] == provider['version'], 'installed-provider-version-license-mismatch')
    require(set(payload['schema']) == set(payload['snapshots']) == set(CONFIG_TABLES + CONFIG_RELATIONS + PAYROLL_TABLES), 'source-schema-snapshot-incomplete')
    headers = {row['id']: row for row in payload['headers']}
    require(len(headers) == len(payload['headers']) == payload['closed_population']['previous_months'], 'closed-cohort-identity-count-differs')
    cutoff = date.fromisoformat(meta['as_of']).replace(day=1)
    require(all(row['state'] in ('done', 'paid') and date.fromisoformat(row['date_to']) < cutoff
        and row['date_from'] <= row['date_to'] for row in headers.values()), 'closed-previous-month-cohort-required')
    seen, issues, concepts = set(), [], {}
    for row in payload['lines']:
        require(row['id'] not in seen and row['slip_id'] in headers, 'stored-line-identity-incomplete')
        seen.add(row['id'])
        if row['salary_rule_id'] is None: issues.append({'line_id': row['id'], 'code': 'RULE_FK_MISSING'})
        for field in ('amount', 'quantity', 'rate', 'total'):
            try: valid = isinstance(row[field], str) and Decimal(row[field]).is_finite()
            except (InvalidOperation, ValueError, TypeError): valid = False
            if not valid: issues.append({'line_id': row['id'], 'code': 'STORED_COMPONENT_NULL_OR_NONFINITE', 'field': field})
        if row['code'] in ('BASIC', 'GROSS', 'NET'):
            concepts.setdefault((row['slip_id'], row['code']), set()).add(row['salary_rule_id'])
    for (slip, code), rules in concepts.items():
        if len(rules) != 1 or None in rules: issues.append({'slip_id': slip, 'concept': code, 'rule_ids': sorted(rules, key=lambda x: x or 0), 'code': 'ESSENTIAL_RULE_IDENTITY_AMBIGUOUS'})
    for ident in headers:
        missing = sorted({'BASIC', 'GROSS', 'NET'} - {code for slip, code in concepts if slip == ident})
        if missing: issues.append({'slip_id': ident, 'concepts': missing, 'code': 'ESSENTIAL_STORED_CONCEPT_MISSING'})
    for name in ('worked_days', 'inputs'):
        seen = set()
        for row in payload[name]:
            require(row['id'] not in seen and row['payslip_id'] in headers, 'stored-child-identity-incomplete')
            seen.add(row['id'])
            if row['type_id'] is None: issues.append({'model': name, 'id': row['id'], 'code': 'TYPED_CHILD_MASTER_MISSING'})
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--cerro-capsule', type=Path, required=True)
    parser.add_argument('--provider-pin', type=Path, default=Path(__file__).with_name('simpledigital_runtime_source.json'))
    parser.add_argument('--as-of', default=date.today().isoformat())
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(os.geteuid() == 0, 'local-peer-capture-requires-root')
    output = args.output.resolve()
    require(output.is_relative_to(Path('/opt/steps-validation')) and not output.exists()
        and output.parent.is_dir() and not args.output.is_symlink(), 'new-private-evidence-path-required')
    capsule_body = args.cerro_capsule.read_bytes()
    require(sha(capsule_body) == CERRO_CAPSULE_SHA256, 'original-cerro-capsule-seal-differs')
    registry_body = args.registry.read_bytes()
    registry = json.loads(registry_body.decode('utf-8-sig'))
    def load(path):
        config = configparser.ConfigParser(interpolation=None)
        require(config.read(path), 'canonical-config-unreadable')
        return config['options']
    database, config_path, roots = resolve_source(registry, load)
    config_hash = sha(Path(config_path).read_bytes())
    pin_body = args.provider_pin.read_bytes(); pin = json.loads(pin_body.decode('utf-8-sig'))
    before = provider_snapshot(roots, pin)
    statement = sql_capture(args.as_of)
    payload = readonly_capture(statement)  # Exactly one connection and one RO transaction; never retry RW.
    issues = validate_payload(payload, before)
    require(before == provider_snapshot(roots, pin) and config_hash == sha(Path(config_path).read_bytes())
        and registry_body == args.registry.read_bytes(), 'runtime-configuration-or-provider-changed-during-capture')
    matrix = compare_rules(json.loads(capsule_body), payload)
    proof = {'schema': 1, 'reference': 'sys_user_approved', 'database': database,
        'atomic_read_only_transaction': True, 'orm_loaded': False, 'payroll_computed': False,
        'database_writes': False, 'formula_bodies_exported': False, 'direct_employee_identifiers_exported': False,
        'contains_private_financial_data': True, 'financial_certified': False, 'master_timeline_certified': False,
        'full_payroll_replay': False, 'identity_conversion': False, 'deadline_resolved': False,
        'registry_sha256': sha(registry_body), 'config_sha256': config_hash,
        'provider_pin_sha256': sha(pin_body), 'provider_source': before,
        'cerro_capsule_sha256': sha(capsule_body), 'tool_sha256': sha(Path(__file__).read_bytes()),
        'sql_sha256': sha(statement.encode()), 'payload': payload, 'stored_data_issues': issues,
        'cerro_rule_coverage': matrix,
        'temporal_unknowns': ['Current contract wage is not an original salary snapshot.',
            'Current formulas/master hashes do not prove their historical versions.',
            'Resolved type codes, calendars and current work entries are not immutable original policy.',
            'Stored totals remain authoritative even when amount*quantity*rate differs by historical rounding.']}
    raw = json.dumps(proof, indent=2, ensure_ascii=False).encode()
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({'file': str(output), 'sha256': sha(raw), 'read_only': True,
        'closed_slips': len(payload['headers']), 'stored_lines': len(payload['lines']),
        'worked_days': len(payload['worked_days']), 'inputs': len(payload['inputs']), 'work_entries': len(payload['work_entries']),
        'data_issues': len(issues), 'cerro_rules': len(matrix),
        'original_xmlid_bindings': sum(row['binding'] == 'same_original_xmlid' for row in matrix),
        'rules_with_stored_coverage': sum(bool(row['stored_line_ids']) for row in matrix), 'financial_certified': False}))


if __name__ == '__main__':
    main()
