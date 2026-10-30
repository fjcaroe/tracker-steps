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


def receipt_profile(passed, mode, operational_extensions=False, quality_extension=False):
    owned_modules(operational_extensions, quality_extension)
    expected = QUALITY_TESTS if quality_extension else EXTENSION_TESTS if operational_extensions else EXPECTED_TESTS
    require(passed.get('quality_extension', False) is quality_extension
        and passed.get('operational_extensions', False) is operational_extensions
        and passed['mode'] == mode and passed['multifront'] is True
        and passed['focused_development_pass'] is False and passed['expected_test_count'] == expected[mode],
        'Exact full MF profile/count receipt required')


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


def verify(proof, mode, source, passed, *, operational_extensions=False, quality_extension=False):
    expected = plan(source, mode, operational_extensions=operational_extensions, quality_extension=quality_extension)
    receipt_profile(passed, mode, operational_extensions, quality_extension)
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
    require(proof['observed'] == observed, 'MF installation observed flags differ')
    return observed


def audit(sql, mode, source, passed, *, operational_extensions=False, quality_extension=False):
    # The callback executes exactly this readonly metadata transaction; there
    # are no dynamic business table names or user values in the query.
    expected = plan(source, mode, operational_extensions=operational_extensions, quality_extension=quality_extension)
    receipt_profile(passed, mode, operational_extensions, quality_extension)
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
    verify(proof, mode, source, passed, operational_extensions=operational_extensions, quality_extension=quality_extension)
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
    for name in ('source', 'passed', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    proof = audit(readonly_sql, args.mode, args.source, json.loads(args.passed.read_text()), operational_extensions=args.operational_extensions, quality_extension=args.quality_extension)
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as stream:
        json.dump(proof, stream, indent=2)
    print('MULTIFRONT_INSTALLATION_VERIFIED', proof['observed']['required_module_versions_verified'], 'exact module versions; readonly')


if __name__ == '__main__':
    main()
