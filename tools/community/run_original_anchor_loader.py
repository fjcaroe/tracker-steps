"""Run the real pinned LGPL loader with two checked, process-local retentions.

The coordinator supplies a new anchored private clone, backups, lease, network
isolation, complete witnesses and already installed SQL guards. This wrapper
does not stage databases, uninstall modules, change source or replace cleanup.
All ordinary installer writes remain the original Odoo CLI's responsibility.
"""
import argparse
import ast
import functools
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import payroll_configuration_adoption_preflight as gate
import retain_original_bootstrap_aliases as retention


PIN = '4b4efe68291d6def5bb7d2e1f2b829e0cda577d4'
MODEL_FILE = 'odoo/addons/base/models/ir_model.py'
MODEL_SHA256 = '43bfd1ebb04688fdb8013f2e941a4c9f39f69a9b4e8ab0d406683908e2ae5b6e'
METHOD_SHA256 = '9d969cfef189aec4a206b2a16f447a0900947d73855198bb88008a42e6ef7366'
TABLES = ('ir_model_data', 'ir_model', 'ir_model_fields', 'ir_model_fields_selection',
          'hr_payroll_structure', 'hr_payroll_structure_type', 'hr_payslip_input_type',
          'hr_salary_rule', 'hr_salary_rule_category', 'ir_act_report_xml', 'res_groups_report_rel')
DATABASE = r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_[A-Za-z0-9_]+'
PRIVATE_ROOT = Path('/opt/steps-validation')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_arguments(arguments):
    gate.require('--' in arguments, 'explicit-odoo-argument-separator-required')
    split = arguments.index('--')
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime', 'capsule', 'identity-before', 'receipt'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('database', 'capsule-sha256', 'identity-before-sha256'):
        parser.add_argument('--' + name, required=True)
    options = parser.parse_args(arguments[:split])
    odoo_args = arguments[split + 1:]
    gate.require(re.fullmatch(DATABASE, options.database), 'new-private-original-handover-required')
    gate.require(options.capsule_sha256 == retention.CAPSULE_SHA256, 'unreviewed-original-capsule-version')
    gate.require(re.fullmatch(r'[0-9a-f]{64}', options.identity_before_sha256), 'identity-before-hash-required')
    gate.require(options.receipt.resolve().is_relative_to(PRIVATE_ROOT)
        and options.receipt.parent.is_dir() and not options.receipt.exists(), 'new-private-loader-receipt-required')
    validate_odoo_arguments(odoo_args, options.database)
    return options, odoo_args


def option_values(arguments, names):
    values = []
    for index, argument in enumerate(arguments):
        if argument in names:
            gate.require(index + 1 < len(arguments) and not arguments[index + 1].startswith('-'), 'missing-odoo-option-value')
            values.append(arguments[index + 1])
        for name in names:
            if name.startswith('--') and argument.startswith(name + '='):
                values.append(argument[len(name) + 1:])
            elif len(name) == 2 and argument.startswith(name) and argument != name:
                # optparse also accepts -dDATABASE / -iMODULE. Do not let an
                # attached later value bypass the single-scope comparison.
                values.append(argument[len(name):])
    return values


def validate_odoo_arguments(arguments, database):
    gate.require(arguments and arguments[0].startswith('-') and '--' not in arguments,
                 'only-real-server-install-arguments-admitted')
    critical = ('--database', '--db-filter', '--workers', '--max-cron-threads',
                '--without-demo', '--stop-after-init', '--no-http', '--init',
                '--test-enable', '--save', '--db_password', '--db-password')
    for argument in arguments:
        name = argument.split('=', 1)[0]
        gate.require(not (name.startswith('--') and any(option.startswith(name)
            and option != name for option in critical)), 'abbreviated-private-scope-options-forbidden')
    expected = [(('-d', '--database'), database), (('--db-filter',), '^' + database + '$'),
                (('--workers',), '0'), (('--max-cron-threads',), '0'), (('--without-demo',), 'all')]
    for names, value in expected:
        gate.require(option_values(arguments, names) == [value], 'explicit-single-private-odoo-scope-required')
    gate.require('--stop-after-init' in arguments and '--no-http' in arguments,
                 'one-shot-no-http-installer-required')
    modules = option_values(arguments, ('-i', '--init'))
    gate.require(len(modules) == 1 and re.fullmatch(r'[a-z_][a-z0-9_]*(?:,[a-z_][a-z0-9_]*)*', modules[0]),
                 'explicit-real-module-install-required')
    gate.require('--test-enable' not in arguments and '--save' not in arguments
        and not any(argument.startswith(('--db_password', '--db-password', '-w')) for argument in arguments),
        'tests-config-writes-or-password-arguments-forbidden')


def validate_runtime(runtime):
    runtime = Path(runtime).resolve()
    git = ['git', '-c', 'safe.directory=' + str(runtime), '-C', str(runtime)]
    gate.require(subprocess.check_output(git + ['rev-parse', 'HEAD'], text=True).strip() == PIN,
                 'official-community-runtime-pin-required')
    gate.require(not subprocess.check_output(git + ['status', '--porcelain'], text=True).strip(),
                 'official-runtime-must-be-clean')
    path = runtime / MODEL_FILE
    raw = path.read_bytes()
    gate.require(raw == subprocess.check_output(git + ['show', PIN + ':' + MODEL_FILE])
        and hashlib.sha256(raw).hexdigest() == MODEL_SHA256, 'official-model-file-does-not-match-pinned-git')
    tree = ast.parse(raw.decode())
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'IrModelData']
    gate.require(len(classes) == 1, 'official-model-data-class-contract')
    methods = [node for node in classes[0].body if isinstance(node, ast.FunctionDef) and node.name == '_process_end']
    gate.require(len(methods) == 1, 'official-cleanup-method-contract')
    method = methods[0]
    gate.require(hashlib.sha256(ast.get_source_segment(raw.decode(), method).encode()).hexdigest() == METHOD_SHA256
        and [value.arg for value in method.args.args] == ['self', 'modules'], 'official-cleanup-source-contract')
    return {'runtime': str(runtime), 'official_pin': PIN, 'ir_model_source_sha256': MODEL_SHA256,
            'original_process_end_sha256': METHOD_SHA256, 'runtime_sources_modified': False}


def check_database_guards(cr):
    cr.execute("SELECT current_setting('session_replication_role')")
    gate.require(cr.fetchall() == [('origin',)], 'original-guard-trigger-role-not-origin')
    cr.execute("SELECT c.relname,t.tgname,t.tgenabled,t.tgtype,p.proname,"
        "md5(p.prosrc) AS guard_function_md5 FROM pg_trigger t "
        "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
        "JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace pn ON pn.oid=p.pronamespace "
        "WHERE n.nspname='public' AND pn.nspname='public' AND NOT t.tgisinternal "
        "AND c.relname=ANY(%s) AND t.tgname IN "
        "('step_anchor_preserve_original_row','step_anchor_preserve_original_truncate',"
        "'step_anchor_preserve_original_insert') ORDER BY c.relname,t.tgname", [list(TABLES)])
    rows = cr.fetchall()
    expected = {(table, name): event for table in TABLES for name, event in (
        ('step_anchor_preserve_original_row', 27), ('step_anchor_preserve_original_truncate', 34))}
    expected['res_groups_report_rel', 'step_anchor_preserve_original_insert'] = 7
    gate.require(len(rows) == len(expected), 'all-original-sql-guards-must-exist')
    actual = set()
    for table, trigger, enabled, events, function, function_md5 in rows:
        gate.require((table, trigger) in expected and (table, trigger) not in actual
            and enabled in ('O', 'A') and events == expected[table, trigger]
            and function == 'step_anchor_guard_' + table
            and re.fullmatch(r'[0-9a-f]{32}', function_md5 or ''), 'original-sql-guard-not-active-or-exact')
        actual.add((table, trigger))
    gate.require(actual == set(expected), 'incomplete-original-sql-guard-set')
    return [{'table': row[0], 'trigger': row[1], 'enabled': row[2],
             'events': row[3], 'function': row[4], 'function_md5': row[5]} for row in rows]


def check_original_report_binding(env):
    gate.require('hr.payslip' in env.registry, 'real-payslip-provider-missing')
    model = env['hr.payslip']
    gate.require(model._table == 'hr_payslip' and model._auto is True
        and model._abstract is False and model._transient is False
        and any(cls.__module__.startswith('odoo.addons.payroll.models.') for cls in type(model).mro()),
        'real-oca-payslip-model-required')
    env.cr.execute("SELECT id,model,state FROM ir_model WHERE id=600 OR model='hr.payslip' ORDER BY id")
    gate.require(env.cr.fetchall() == [(600, 'hr.payslip', 'base')], 'original-payslip-binding-600-not-preserved')
    env.cr.execute('SELECT id,type,model,report_type,report_name,binding_model_id '
                   'FROM ir_act_report_xml WHERE id=462')
    gate.require(env.cr.fetchall() == [(462, 'ir.actions.report', 'hr.payslip', 'qweb-pdf',
        'hr_payroll.report_payslip_lang', 600)], 'original-report-462-core-identity-not-preserved')


def install_wrapper(ir_model, options, calls):
    original = ir_model.IrModelData._process_end
    expected_file = (options.runtime.resolve() / MODEL_FILE).resolve()
    gate.require(tuple(inspect.signature(original).parameters) == ('self', 'modules')
        and getattr(original, '_api', None) == 'model'
        and Path(inspect.getsourcefile(original)).resolve() == expected_file
        and not getattr(original, '_step_original_anchor_wrapper', False), 'actual-original-cleanup-callable-required')

    @functools.wraps(original)
    def process_end(self, modules):
        gate.require(self.env.cr.dbname == options.database, 'cleanup-outside-private-anchor-forbidden')
        gate.require(type(modules) in (list, tuple, set) and modules
            and all(isinstance(name, str) and re.fullmatch(r'[a-z_][a-z0-9_]*', name) for name in modules),
            'real-processed-module-list-required')
        guards = check_database_guards(self.env.cr)
        check_original_report_binding(self.env)
        proof = retention.retain_original_aliases(self.env, capsule_path=options.capsule,
            capsule_sha256=options.capsule_sha256, original_identity_path=options.identity_before,
            original_identity_sha256=options.identity_before_sha256)
        record = {'database': options.database, 'processed_modules': list(modules),
            'guards': guards, 'retention': proof, 'original_payslip_model_id': 600,
            'original_report_id': 462, 'original_cleanup_delegated': False}
        result = original(self, modules)  # No skips, namespace pruning or fake success.
        record['original_cleanup_delegated'] = True
        record['original_cleanup_cleared_loaded_set'] = not self.env.registry.loaded_xmlids
        calls.append(record)
        return result

    process_end._step_original_anchor_wrapper = True
    ir_model.IrModelData._process_end = process_end
    return original


def main(arguments=None):
    options, odoo_args = parse_arguments(list(sys.argv[1:] if arguments is None else arguments))
    proof = validate_runtime(options.runtime)
    # Check sealed private source bytes before the original CLI can start.
    retention._read_sealed(options.capsule, options.capsule_sha256)
    retention._read_sealed(options.identity_before, options.identity_before_sha256)
    gate.require(not any(name == 'odoo' or name.startswith('odoo.') for name in sys.modules),
                 'fresh-standalone-loader-process-required')
    os.environ['TZ'] = 'UTC'
    if hasattr(time, 'tzset'): time.tzset()
    sys.path.insert(0, str(options.runtime.resolve()))
    import odoo
    gate.require(Path(odoo.__file__).resolve() == options.runtime.resolve() / 'odoo/__init__.py',
                 'imported-odoo-is-not-the-admitted-runtime')
    from odoo.addons.base.models import ir_model
    calls = []
    install_wrapper(ir_model, options, calls)
    sys.argv = [str(options.runtime.resolve() / 'odoo-bin'), *odoo_args]
    try:
        odoo.cli.main()
    except SystemExit as result:
        if result.code not in (None, 0):
            raise
    gate.require(calls and all(row['original_cleanup_delegated']
        and row['original_cleanup_cleared_loaded_set'] for row in calls), 'original-cleanup-success-not-observed')
    receipt = {'schema': 1, **proof, 'database': options.database,
        'calls': calls, 'original_cleanup_delegated': True,
        'exact_two_original_aliases_retained_per_call': True,
        'wrapper_process_only': True, 'installed_sources_modified': False,
        'wrapper_sha256': sha(__file__), 'retention_helper_sha256': sha(retention.__file__),
        'sql_helper_sha256': sha(gate.__file__), 'capsule_sha256': options.capsule_sha256,
        'identity_before_sha256': options.identity_before_sha256,
        'odoo_argv_sha256': hashlib.sha256(json.dumps(odoo_args).encode()).hexdigest(),
        'adoption_complete': False, 'financial_certified': False, 'production_cutover': False}
    with os.fdopen(os.open(options.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
