"""Readonly postflight of the exact MF installed module/provider contract.

Standalone metadata SELECT only: no ORM, business rows, upgrades or EE bodies.
The postflight tool can live outside the immutable tested addon source tree.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


OWN_MODULES = (
    'step_payroll_contracts', 'step_payroll_oca_api', 'step_payroll_enterprise_reference',
    'step_simpledigital_oca_base', 'step_simpledigital_oca_security',
    'step_hr_contract_lifecycle', 'step_hr_contract_lifecycle_simpledigital',
    'step_payroll_engine_transition', 'steps_hr_payroll_correction', 'step_payroll_batch_period',
    'step_accounting_multicurrency_core', 'step_account_balance_analytic', 'step_bank_export_core',
    'step_account_treasury_batch', 'step_bank_security', 'step_accounting_multicurrency',
    'step_l10n_cl_edi_core', 'step_l10n_cl_caf_custody_core', 'step_l10n_cl_caf_storage',
    'step_l10n_cl_caf_native_reference', 'step_batch_payment_grouping', 'step_batch_payment_core',
    'step_account_treasury', 'step_treasury_community_reports', 'step_account_treasury_reports',
    'step_hr_contract_days', 'step_hr_contract_days_oca',
)
EXCLUDED = {
    'community': {'step_payroll_enterprise_reference', 'step_l10n_cl_caf_native_reference',
                  'step_account_treasury_batch', 'step_bank_security', 'step_accounting_multicurrency'},
    'cerro-reference': {'step_payroll_oca_api', 'step_simpledigital_oca_base',
                        'step_l10n_cl_caf_storage', 'step_batch_payment_core', 'step_hr_contract_days_oca'},
}
OCA_PIN = '4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e'
# Manifest metadata read from that pinned LGPL source, not inferred from DB.
OCA_VERSIONS = {'payroll': '18.0.1.4.0', 'payroll_account': '18.0.1.0.6'}
NATIVE_ENGINES = {'hr_payroll', 'hr_payroll_account'}
PROVIDER = 'l10n_cl_simpledigital_payroll'
EXPECTED_TESTS = {'community': 576, 'cerro-reference': 391}
EXTENSION_MODULES = ('step_payroll_advantages_oca', 'step_payroll_benefits_native_reference', 'step_payroll_original_report')
EXTENSION_TESTS = {'community': 637, 'cerro-reference': 437}
EXTENSION_OCA_VERSIONS = dict(OCA_VERSIONS, payroll_contract_advantages='18.0.1.0.0')
QUALITY_MODULES = ('step_quality_contracts', 'step_quality_oca', 'step_qa_native_reference')
QUALITY_TESTS = {'community': 646, 'cerro-reference': 441}
CRITICAL_TESTS = {'community': 665, 'cerro-reference': 457}
CRITICAL_GENERATIONS = {'R3': CRITICAL_TESTS, 'S': {'community': 671, 'cerro-reference': 462},
    'T': {'community': 671, 'cerro-reference': 462}}
S_VERSIONS = {'step_payroll_contracts': '18.0.1.15.0', 'step_payroll_oca_api': '18.0.1.16.0'}
T_VERSIONS = {'step_payroll_contracts': '18.0.1.16.0', 'step_payroll_oca_api': '18.0.1.16.0'}
GENERATION_VERSIONS = {'S': S_VERSIONS, 'T': T_VERSIONS}
QUALITY_PROVIDER = 'quality_control_oca'
QUALITY_PIN = '2d6084f553490408f7a341f05ba6ddd6e641a879'
QUALITY_VERSION = '18.0.1.4.0'
QUERY = """BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT json_build_object(
 'database',current_database(),'transaction_read_only',current_setting('transaction_read_only'),
 'installed',(SELECT coalesce(json_agg(t ORDER BY t.name),'[]'::json) FROM
   (SELECT name,latest_version,license,state FROM ir_module_module WHERE state='installed') t),
 'pending',(SELECT coalesce(json_agg(t ORDER BY t.name),'[]'::json) FROM
   (SELECT name,latest_version,license,state FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')) t),
 'payslip_models',(SELECT coalesce(json_agg(t ORDER BY t.id),'[]'::json) FROM
   (SELECT id,model FROM ir_model WHERE model='hr.payslip') t),
 'payslip_model_aliases',(SELECT coalesce(json_agg(t ORDER BY t.module),'[]'::json) FROM
   (SELECT id,module,name,model,res_id,noupdate FROM ir_model_data
     WHERE module IN ('payroll','hr_payroll') AND name='model_hr_payslip') t),
 'payslip_table_exists',to_regclass('public.hr_payslip') IS NOT NULL);
ROLLBACK;"""


SECURITY_GROUP_FK_QUERY = """BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT json_build_object('database',current_database(),
 'transaction_read_only',current_setting('transaction_read_only'),
 'default_transaction_read_only',current_setting('default_transaction_read_only'),
 'table',(SELECT json_build_object('schema',n.nspname,'name',c.relname,'kind',c.relkind)
   FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.oid=to_regclass('public.rule_group_rel')),
 'column',(SELECT json_build_object('name',a.attname,'sql_type',format_type(a.atttypid,a.atttypmod),'not_null',a.attnotnull)
   FROM pg_attribute a WHERE a.attrelid=to_regclass('public.rule_group_rel') AND a.attname='group_id' AND NOT a.attisdropped),
 'models',(SELECT coalesce(json_agg(json_build_object('id',id,'model',model) ORDER BY model),'[]'::json)
   FROM ir_model WHERE model IN ('ir.rule','res.groups')),
 'fields',(SELECT coalesce(json_agg(json_build_object('id',f.id,'model',f.model,'name',f.name,
     'ttype',f.ttype,'relation',f.relation,'store',f.store) ORDER BY f.model,f.name),'[]'::json)
   FROM ir_model_fields f WHERE (f.model='ir.rule' AND f.name='groups') OR (f.model='res.groups' AND f.name='rule_groups')),
 'foreign_keys',(SELECT coalesce(json_agg(json_build_object('oid',k.oid::bigint,'name',k.conname,
   'source_columns',(SELECT array_agg(a.attname ORDER BY x.ord) FROM unnest(k.conkey) WITH ORDINALITY x(attnum,ord)
     JOIN pg_attribute a ON a.attrelid=k.conrelid AND a.attnum=x.attnum),
   'target_schema',rn.nspname,'target_table',rc.relname,
   'target_columns',(SELECT array_agg(a.attname ORDER BY x.ord) FROM unnest(k.confkey) WITH ORDINALITY x(attnum,ord)
     JOIN pg_attribute a ON a.attrelid=k.confrelid AND a.attnum=x.attnum),
   'on_delete',k.confdeltype,'on_update',k.confupdtype,'match',k.confmatchtype,
   'validated',k.convalidated,'deferrable',k.condeferrable,'deferred',k.condeferred,
   'definition',pg_get_constraintdef(k.oid)) ORDER BY k.oid),'[]'::json)
   FROM pg_constraint k JOIN pg_class rc ON rc.oid=k.confrelid JOIN pg_namespace rn ON rn.oid=rc.relnamespace
   WHERE k.conrelid=to_regclass('public.rule_group_rel') AND k.contype='f'
     AND EXISTS(SELECT 1 FROM unnest(k.conkey) key(attnum) JOIN pg_attribute a
       ON a.attrelid=k.conrelid AND a.attnum=key.attnum WHERE a.attname='group_id')));
ROLLBACK;"""
SECURITY_GROUP_FK_NAME = 'rule_group_rel_group_id_fkey'


def verify_security_group_fk(capture, database, phase):
    require(isinstance(capture, dict), 'Actual security FK capture required')
    require(capture.get('schema') == 1 and capture.get('database') == database and capture.get('phase') == phase
        and capture.get('query_sha256') == sha(SECURITY_GROUP_FK_QUERY.encode())
        and capture.get('read_only') is True and capture.get('database_writes') is False
        and capture.get('orm_loaded') is False and capture.get('manual_ddl_performed_by_helper') is False,
        'Exact readonly security FK capture required')
    meta = capture['metadata']
    require(meta['database'] == database and meta['transaction_read_only'] == meta['default_transaction_read_only'] == 'on',
        'Security FK readonly transaction not proven')
    require(meta['table'] == {'schema':'public','name':'rule_group_rel','kind':'r'}
        and meta['column'] == {'name':'group_id','sql_type':'integer','not_null':True},
        'Security relation physical column differs')
    require(len(meta['models']) == 2 and {row['model'] for row in meta['models']} == {'ir.rule','res.groups'}
        and len({row['id'] for row in meta['models']}) == 2
        and all(type(row['id']) is int and row['id'] > 0 for row in meta['models']), 'Security model identities differ')
    expected_fields = {('ir.rule','groups','many2many','res.groups',True), ('res.groups','rule_groups','many2many','ir.rule',True)}
    require(len(meta['fields']) == 2 and {(row['model'],row['name'],row['ttype'],row['relation'],row['store']) for row in meta['fields']} == expected_fields
        and len({row['id'] for row in meta['fields']}) == 2 and all(type(row['id']) is int and row['id'] > 0 for row in meta['fields']),
        'Security inverse field identities/types differ')
    require(len(meta['foreign_keys']) == 1, 'One physical security group FK required')
    fk = meta['foreign_keys'][0]
    require(type(fk['oid']) is int and fk['oid'] > 0 and fk['name'] == SECURITY_GROUP_FK_NAME
        and fk['source_columns'] == ['group_id'] and fk['target_schema'] == 'public'
        and fk['target_table'] == 'res_groups' and fk['target_columns'] == ['id']
        and fk['on_delete'] == 'r' and fk['on_update'] == 'a' and fk['match'] == 's'
        and fk['validated'] is True and fk['deferrable'] is False and fk['deferred'] is False
        and fk['definition'] == 'FOREIGN KEY (group_id) REFERENCES res_groups(id) ON DELETE RESTRICT',
        'Original validated RESTRICT security group FK required')
    return {key:value for key,value in meta.items() if key not in ('database','transaction_read_only','default_transaction_read_only')} | {
        'foreign_keys':[{key:value for key,value in fk.items() if key != 'oid'}]}


def capture_security_group_fk(sql, database, phase):
    require(re.fullmatch(r'(?:COMMUNITY_PAYROLL_API_|MANAGEMENT_QA_CERRO_PAYROLL_API_)[A-Za-z0-9_]+', database),
        'Private security FK capture database required')
    proof = {'schema':1,'database':database,'phase':phase,'query_sha256':sha(SECURITY_GROUP_FK_QUERY.encode()),
        'read_only':True,'database_writes':False,'orm_loaded':False,'manual_ddl_performed_by_helper':False,
        'metadata':json.loads(sql(database, SECURITY_GROUP_FK_QUERY))}
    verify_security_group_fk(proof,database,phase)
    return proof


def verify_security_group_fk_boundary(boundary, mode, database, current):
    require(isinstance(boundary, dict) and {'recorded_under_shared_environment_lease','manual_security_ddl_performed_by_validator',
        'after_tests','after_tests_sha256','before_native_upgrade','after_native_upgrade',
        'before_native_upgrade_sha256','after_native_upgrade_sha256'} <= boundary.keys(), 'Complete security FK boundary required')
    require(boundary['recorded_under_shared_environment_lease'] is True
        and boundary['manual_security_ddl_performed_by_validator'] is False,
        'Security FK boundary requires the actual shared upgrade lease and no manual DDL')
    after = boundary['after_tests']
    after_semantics = verify_security_group_fk(after,database,'after-tests')
    require(boundary['after_tests_sha256'] == sha(json.dumps(after,indent=2).encode()), 'Security FK after-tests seal differs')
    current_semantics = verify_security_group_fk(current,database,'postflight')
    require(current_semantics == after_semantics, 'Security FK drifted after tested registry')
    before = boundary['before_native_upgrade']
    upgrade = boundary['after_native_upgrade']
    if mode == 'community':
        require(before is None and upgrade is None and boundary['before_native_upgrade_sha256'] is None
            and boundary['after_native_upgrade_sha256'] is None, 'Cold Community cannot claim a native FK baseline')
        baseline_oid = None
    else:
        before_semantics = verify_security_group_fk(before,database,'before-native-upgrade')
        upgrade_semantics = verify_security_group_fk(upgrade,database,'after-native-upgrade')
        require(before_semantics == upgrade_semantics == after_semantics,
            'Original native security FK semantics or identities changed during upgrade')
        require(boundary['before_native_upgrade_sha256'] == sha(json.dumps(before,indent=2).encode())
            and boundary['after_native_upgrade_sha256'] == sha(json.dumps(upgrade,indent=2).encode()), 'Security FK native baseline seal differs')
        baseline_oid = before['metadata']['foreign_keys'][0]['oid']
    return {'on_delete':'RESTRICT','validated':True,'deferrable':False,'deferred':False,
        'source_columns':['group_id'],'target_table':'public.res_groups','target_columns':['id'],
        'constraint_name':SECURITY_GROUP_FK_NAME,'native_before_upgrade_baseline':mode != 'community',
        'baseline_constraint_oid':baseline_oid,'postflight_constraint_oid':current['metadata']['foreign_keys'][0]['oid'],
        'constraint_oid_unchanged':None if baseline_oid is None else baseline_oid == current['metadata']['foreign_keys'][0]['oid'],
        'constraint_oid_is_business_identity_gate':False,'semantics_and_model_field_identities_preserved':True,
        'manual_security_ddl_performed_by_validator':False}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def _body(source, name):
    if isinstance(source, dict):
        require(name in source and isinstance(source[name], bytes), 'Trusted manifest source missing: ' + name)
        return source[name]
    path = Path(source) / name
    require(path.is_file() and not path.is_symlink(), 'Manifest is not a regular source file: ' + name)
    return path.read_bytes()


def owned_modules(operational_extensions=False, quality_extension=False):
    require(type(operational_extensions) is bool, 'Explicit operational extension profile required')
    require(type(quality_extension) is bool and (not quality_extension or operational_extensions), 'Quality requires explicit operational extensions')
    return OWN_MODULES + (EXTENSION_MODULES if operational_extensions else ()) + (QUALITY_MODULES if quality_extension else ())


def mode_excluded(mode, operational_extensions=False, quality_extension=False):
    value = set(EXCLUDED[mode])
    if operational_extensions:
        value.add('step_payroll_benefits_native_reference' if mode == 'community' else 'step_payroll_advantages_oca')
    if quality_extension:
        value.add('step_qa_native_reference' if mode == 'community' else 'step_quality_oca')
    return value


def critical_tests(critical_extension=False, critical_generation='R3'):
    require(type(critical_extension) is bool and critical_generation in CRITICAL_GENERATIONS
        and (critical_extension or critical_generation == 'R3'),
        'Explicit supported critical generation required')
    return CRITICAL_GENERATIONS[critical_generation]


def check_generation(receipt, critical_extension=False, critical_generation='R3'):
    critical_tests(critical_extension, critical_generation)
    require(receipt.get('critical_generation', 'R3') == critical_generation,
        'Critical receipt/proof generation differs')


def receipt_profile(passed, mode, operational_extensions=False, quality_extension=False, critical_extension=False, critical_generation='R3'):
    owned_modules(operational_extensions, quality_extension)
    require(type(critical_extension) is bool and (not critical_extension or quality_extension), 'Critical requires the exact Quality extension')
    expected = critical_tests(critical_extension, critical_generation) if critical_extension else QUALITY_TESTS if quality_extension else EXTENSION_TESTS if operational_extensions else EXPECTED_TESTS
    check_generation(passed, critical_extension, critical_generation)
    require(passed.get('critical_extension', False) is critical_extension, 'Exact critical profile flag required')
    require(passed.get('quality_extension', False) is quality_extension
        and passed.get('operational_extensions', False) is operational_extensions
        and passed['mode'] == mode and passed['multifront'] is True
        and passed['focused_development_pass'] is False and passed['expected_test_count'] == expected[mode],
        'Exact full MF profile/count receipt required')
    if critical_generation in GENERATION_VERSIONS:
        require(passed.get('package_files') == 513, 'S requires the exact 513-file normal provider package')


def plan(source, mode, *, operational_extensions=False, quality_extension=False):
    require(mode in EXCLUDED, 'Unknown MF installation mode')
    manifests, expected, fingerprints = {}, {}, {}
    modules = owned_modules(operational_extensions, quality_extension)
    excluded = mode_excluded(mode, operational_extensions, quality_extension)
    oca_versions = EXTENSION_OCA_VERSIONS if operational_extensions else OCA_VERSIONS
    required_owned = 26 if quality_extension else 24 if operational_extensions else 22
    for module in modules:
        name = module + '/__manifest__.py'
        body = _body(source, name)
        spec = ast.literal_eval(body.decode('utf-8-sig'))
        require(spec['license'] in ('LGPL-3', 'AGPL-3') and isinstance(spec['version'], str), 'Nonfree/invalid owned manifest')
        manifests[module] = spec
        fingerprints[name] = sha(body)
        if module not in excluded:
            expected[module] = {'version': spec['version'], 'license': spec['license']}
    require(len(modules) == (33 if quality_extension else 30 if operational_extensions else 27) and len(expected) == required_owned, 'MF mode-owned module plan changed')
    if mode == 'community':
        body = _body(source, PROVIDER + '/__manifest__.py')
        provider = ast.literal_eval(body.decode('utf-8-sig'))
        require(provider['license'] == 'AGPL-3' and provider['depends'] == ['step_simpledigital_oca_base'],
                'Real normal Community provider manifest required')
        fingerprints[PROVIDER + '/__manifest__.py'] = sha(body)
        expected[PROVIDER] = {'version': provider['version'], 'license': 'AGPL-3'}
        expected.update({module: {'version': version, 'license': 'LGPL-3'} for module, version in oca_versions.items()})
        if quality_extension:
            expected[QUALITY_PROVIDER] = {'version': QUALITY_VERSION, 'license': 'AGPL-3'}
        forbidden = excluded | NATIVE_ENGINES | {'account_reports', 'account_accountant', 'account_batch_payment'}
    else:
        name = 'tools/community/simpledigital_runtime_source.json'
        body = _body(source, name); pin = json.loads(body.decode('utf-8-sig'))
        require(pin['license'] == 'AGPL-3' and len(pin['files']) == 52, 'Original native AGPL provider pin required')
        fingerprints[name] = sha(body)
        expected[PROVIDER] = {'version': pin['version'], 'license': pin['license']}
        forbidden = excluded | set(oca_versions) | ({QUALITY_PROVIDER} if quality_extension else set())
    result = {'required': expected, 'forbidden': sorted(forbidden), 'owned_required': required_owned,
              'source_manifest_sha256': fingerprints, 'oca_pin': OCA_PIN}
    if operational_extensions:
        result['operational_extensions'] = True
    if quality_extension:
        result.update(quality_extension=True, quality_vendor_pin=QUALITY_PIN)
    return result


def verify(proof, mode, source, passed, *, operational_extensions=False, quality_extension=False, critical_extension=False, critical_generation='R3'):
    expected = plan(source, mode, operational_extensions=operational_extensions, quality_extension=quality_extension)
    receipt_profile(passed, mode, operational_extensions, quality_extension, critical_extension, critical_generation)
    check_generation(proof, critical_extension, critical_generation)
    if critical_generation in GENERATION_VERSIONS:
        for module, version in GENERATION_VERSIONS[critical_generation].items():
            require(ast.literal_eval(_body(source, module + '/__manifest__.py').decode('utf-8-sig'))['version'] == version,
                critical_generation + ' original-interface source version differs: ' + module)
    require(proof.get('critical_extension', False) is critical_extension, 'Exact critical postflight flag required')
    require(proof.get('quality_extension', False) is quality_extension
        and proof.get('operational_extensions', False) is operational_extensions and passed['writes_to_source'] is False,
            'Full accepted MF receipt required for installation postflight')
    prefix = 'COMMUNITY_PAYROLL_API_' if mode == 'community' else 'MANAGEMENT_QA_CERRO_PAYROLL_API_'
    require(re.fullmatch(prefix + r'[A-Za-z0-9_]+', passed['database']), 'Private MF database required')
    require(proof['schema'] == 1 and proof['mode'] == mode and proof['database'] == passed['database']
            and proof['read_only'] is True and proof['database_writes'] is False and proof['orm_loaded'] is False,
            'MF installation custody/scope differs')
    require(proof['query_sha256'] == sha(QUERY.encode()) and proof['plan'] == expected, 'MF installation source plan/query differs')
    data = proof['metadata']
    require(data['database'] == passed['database'] and data['transaction_read_only'] == 'on', 'Readonly private metadata transaction not proven')
    installed = {row['name']: row for row in data['installed']}
    if not operational_extensions:
        require(not set(installed) & (set(EXTENSION_MODULES) | {'payroll_contract_advantages'}),
            'Operational extension modules require their explicit profile')
    if not quality_extension:
        require(not set(installed) & (set(QUALITY_MODULES) | {QUALITY_PROVIDER}), 'Quality modules require their explicit profile')
    require(len(installed) == len(data['installed']) and all(row['state'] == 'installed' for row in installed.values()), 'Installed module identities/states differ')
    graph = {'installed': len(installed), 'enterprise': sum(row['license'] == 'OEEL-1' for row in installed.values())}
    require(graph == passed['counts'] and graph['enterprise'] == (0 if mode == 'community' else 140), 'Actual module graph differs from accepted receipt')
    for name, contract in expected['required'].items():
        row = installed.get(name)
        require(row is not None and row['latest_version'] == contract['version'] and row['license'] == contract['license'],
                'Required MF module missing, wrong version or license: ' + name)
    require(not (set(installed) & set(expected['forbidden'])), 'Incompatible MF mode/provider module installed')
    require(not any(row['name'] in expected['required'] or row['name'] in expected['forbidden']
                    or mode == 'community' and row['license'] == 'OEEL-1' for row in data['pending']),
            'MF required/forbidden provider has a pending operation')
    if mode == 'community':
        require(not any(row['license'] == 'OEEL-1' for row in installed.values()), 'Enterprise is installed in Community')
        owner, engines = 'payroll', set(OCA_VERSIONS)
    else:
        owner, engines = 'hr_payroll', NATIVE_ENGINES
        require(all(name in installed and installed[name]['license'] == 'OEEL-1' for name in engines), 'Original native payroll engines are not retained')
    require(data['payslip_table_exists'] is True and len(data['payslip_models']) == 1
            and data['payslip_models'][0]['model'] == 'hr.payslip', 'Real single payslip model/table required')
    aliases = [row for row in data['payslip_model_aliases'] if row['module'] == owner]
    require(all(row['module'] in ('payroll', 'hr_payroll') and row['name'] == 'model_hr_payslip'
                and row['model'] == 'ir.model' and row['res_id'] == data['payslip_models'][0]['id']
                for row in data['payslip_model_aliases']), 'A payslip provider alias targets another identity')
    require(len(aliases) == 1 and aliases[0]['model'] == 'ir.model'
            and aliases[0]['res_id'] == data['payslip_models'][0]['id'], 'Payslip provider model identity differs')
    observed = {'counts': graph, 'owned_required_versions_verified': expected['owned_required'],
                'required_module_versions_verified': len(expected['required']),
                'engine_modules': {name: installed[name]['latest_version'] for name in sorted(engines)},
                'community_engine_installed': mode == 'community', 'native_engine_retained': mode != 'community',
                'native_reference_only': mode != 'community', 'registry_class_introspection': False,
                'historical_conversion': False, 'production_changed': False}
    if critical_generation == 'T':
        observed['security_group_fk'] = verify_security_group_fk_boundary(passed['security_group_fk_boundary'], mode, passed['database'], proof['security_group_fk_after'])
    require(proof['observed'] == observed, 'MF installation observed flags differ')
    return observed


def audit(sql, mode, source, passed, *, operational_extensions=False, quality_extension=False, critical_extension=False, critical_generation='R3'):
    # The callback executes exactly this readonly metadata transaction; there
    # are no dynamic business table names or user values in the query.
    expected = plan(source, mode, operational_extensions=operational_extensions, quality_extension=quality_extension)
    receipt_profile(passed, mode, operational_extensions, quality_extension, critical_extension, critical_generation)
    prefix = 'COMMUNITY_PAYROLL_API_' if mode == 'community' else 'MANAGEMENT_QA_CERRO_PAYROLL_API_'
    require(re.fullmatch(prefix + r'[A-Za-z0-9_]+', passed['database']), 'Private MF database required')
    metadata = json.loads(sql(passed['database'], QUERY))
    installed = {row['name']: row for row in metadata['installed']}
    engines = set(OCA_VERSIONS) if mode == 'community' else NATIVE_ENGINES
    proof = {'schema': 1, 'mode': mode, 'database': passed['database'], 'read_only': True,
             'database_writes': False, 'orm_loaded': False, 'query_sha256': sha(QUERY.encode()),
             'tool_sha256': sha(Path(__file__).read_bytes()), 'plan': expected, 'metadata': metadata,
             'observed': {'counts': {'installed': len(installed), 'enterprise': sum(row['license'] == 'OEEL-1' for row in installed.values())},
                'owned_required_versions_verified': expected['owned_required'], 'required_module_versions_verified': len(expected['required']),
                'engine_modules': {name: installed[name]['latest_version'] for name in sorted(engines) if name in installed},
                'community_engine_installed': mode == 'community', 'native_engine_retained': mode != 'community',
                'native_reference_only': mode != 'community', 'registry_class_introspection': False,
                'historical_conversion': False, 'production_changed': False}}
    if operational_extensions:
        proof['operational_extensions'] = True
    if quality_extension:
        proof['quality_extension'] = True
    if critical_extension:
        proof['critical_extension'] = True
    if critical_generation in GENERATION_VERSIONS:
        proof['critical_generation'] = critical_generation
    if critical_generation == 'T':
        proof['security_group_fk_after'] = capture_security_group_fk(sql, passed['database'], 'postflight')
        proof['observed']['security_group_fk'] = verify_security_group_fk_boundary(passed['security_group_fk_boundary'], mode, passed['database'], proof['security_group_fk_after'])
    verify(proof, mode, source, passed, operational_extensions=operational_extensions, quality_extension=quality_extension, critical_extension=critical_extension, critical_generation=critical_generation)
    return proof


def readonly_sql(database, statement):
    result = subprocess.run(['sudo', '-u', 'postgres', 'env', 'PGHOST=/var/run/postgresql',
        'PGOPTIONS=-c default_transaction_read_only=on', 'PGPASSFILE=/opt/steps-validation/no-such-readonly-passfile',
        'psql', '-XAtq', '-v', 'ON_ERROR_STOP=1', '-d', database], input=statement, text=True, capture_output=True)
    require(result.returncode == 0, 'Readonly module metadata query failed; raw diagnostics withheld')
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=EXCLUDED)
    parser.add_argument('--operational-extensions', action='store_true')
    parser.add_argument('--quality-extension', action='store_true')
    parser.add_argument('--critical-extension', action='store_true')
    parser.add_argument('--critical-generation', choices=CRITICAL_GENERATIONS, default='R3')
    for name in ('source', 'passed', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    proof = audit(readonly_sql, args.mode, args.source, json.loads(args.passed.read_text()), operational_extensions=args.operational_extensions, quality_extension=args.quality_extension, critical_extension=args.critical_extension, critical_generation=args.critical_generation)
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as stream:
        json.dump(proof, stream, indent=2)
    print('MULTIFRONT_INSTALLATION_VERIFIED', proof['observed']['required_module_versions_verified'], 'exact module versions; readonly')


if __name__ == '__main__':
    main()
