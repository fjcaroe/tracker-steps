"""Read-only checkpoints for an original-identity, seedless payroll bootstrap.

No Odoo import, DDL/DML, sequence allocation/reservation, relocation or writer.
Module manifests describe the dependency minimum, not the actual auto-install
graph or numeric allocations. Only observed checkpoints can establish vacancy.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import xml.etree.ElementTree as ET

import payroll_configuration_adoption_preflight as gate


REFERENCE_ALIASES = {('step_simpledigital_oca_security', 'chile_rule_' + name)
                     for name in ('basic', 'gross', 'net')}
TYPE_ALIASES = tuple(('hr_contract', name) for name in (
    'structure_type_employee', 'structure_type_worker',
    'structure_type_employee_cp200_pfi', 'structure_type_employee_cp200'))
LEGACY_REPORT = ('hr_payroll', 'action_report_payslip')
IDENTITY_COLUMNS = ('id', 'module', 'name', 'model', 'res_id', 'noupdate')
OFFICIAL_PIN = '4b4efe68291d6def5bb7d2e1f2b829e0cda577d4'
OCA_PIN = '4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key(row):
    return row['module'], row['name']


def original_aliases(capsule, identity):
    """The three reference aliases must never acquire original metadata PKs."""
    gate.capsule_rows(capsule)
    original = {key(row): row for row in identity['original_xmlids']}
    gate.require(len(original) == len(identity['original_xmlids']), 'duplicate-original-alias')
    selected = []
    for row in capsule['xmlids']:
        if key(row) in REFERENCE_ALIASES:
            gate.require(key(row) not in original, 'reference-alias-already-in-original')
            continue
        before = original.get(key(row))
        gate.require(before is not None and all(before.get(name) == row[name]
            for name in IDENTITY_COLUMNS), 'original-alias-identity-or-noupdate-drift')
        selected.append({name: row[name] for name in IDENTITY_COLUMNS})
    gate.require(len(selected) == 88 and len(capsule['xmlids']) == 91,
                 'expected-88-original-and-three-reference-aliases')
    gate.require(len({row['id'] for row in selected}) == 88, 'duplicate-original-metadata-pk')
    return sorted(selected, key=lambda row: row['id'])


def source_report(external, identity):
    """Accept metadata already captured by the SQL-only source preflight."""
    reports = external['source_external_metadata']['external:ir_act_report_xml']
    gate.require(len(reports) == 1, 'ambiguous-original-report-contract')
    row = reports[0]
    gate.require(row['id'] == 462 and row['model'] == 'hr.payslip'
        and row['report_type'] == 'qweb-pdf'
        and row['report_name'] == 'hr_payroll.report_payslip_lang'
        and type(row['binding_model_id']) is int and row['binding_model_id'] > 0,
        'unexpected-original-report-contract')
    aliases = {key(value): value for value in identity['original_xmlids']}
    alias = aliases.get(LEGACY_REPORT)
    gate.require(alias is not None and alias['model'] == 'ir.actions.report'
        and alias['res_id'] == 462 and type(alias.get('noupdate')) is bool,
        'original-report-alias-not-proven')
    models = [value for value in identity['ir_model'] if value['id'] == row['binding_model_id']
              or value['model'] == 'hr.payslip']
    gate.require(len(models) == 1 and models[0]['id'] == row['binding_model_id']
        and models[0]['model'] == 'hr.payslip' and models[0]['transient'] is False,
        'original-binding-model-identity-not-proven')
    return dict(row, original_alias={name: alias[name] for name in IDENTITY_COLUMNS})


def dependency_minimum(roots, requested):
    """Inspect only free manifests/data; do not execute source or claim IDs.

    Graph iteration in the pinned LGPL runtime is by dependency depth, then
    module name. Auto-install modules can enlarge this minimum; the real log
    and checkpoint remain mandatory. A CLI -i list is not a load-order policy.
    """
    modules = {}

    def visit(name):
        gate.require(re.fullmatch(r'[a-z_][a-z0-9_]*', name), 'unsafe-module-name')
        if name in modules:
            gate.require(modules[name] is not None, 'cyclic-module-dependency')
            return
        candidates = [Path(root) / name for root in roots
                      if (Path(root) / name / '__manifest__.py').is_file()]
        gate.require(len(candidates) == 1, 'missing-or-shadowed-module-source')
        folder = candidates[0]
        manifest = folder / '__manifest__.py'
        spec = ast.literal_eval(manifest.read_text(encoding='utf-8-sig'))
        gate.require(spec.get('license', 'LGPL-3') in ('LGPL-3', 'AGPL-3'),
                     'nonfree-module-source-not-readable')
        modules[name] = None
        for dependency in spec.get('depends', []):
            visit(dependency)
        files, definitions = [], []
        for filename in spec.get('data', []):
            path = Path(filename)
            gate.require(not path.is_absolute() and '..' not in path.parts,
                         'unsafe-manifest-data-path')
            source = folder / path
            gate.require(source.is_file(), 'missing-manifest-data')
            files.append({'file': filename, 'sha256': sha(source)})
            if source.suffix == '.xml':
                for node in ET.fromstring(source.read_bytes()).iter():
                    model = node.get('model')
                    if node.tag == 'report':
                        model = 'ir.actions.report'
                    if node.get('id') and (model in gate.TABLES.values()
                                           or (model or '').startswith('ir.actions.')):
                        xmlid = node.get('id')
                        definitions.append({'file': filename, 'model': model,
                            'xmlid': xmlid if '.' in xmlid else name + '.' + xmlid})
        depth = max((modules[value]['depth'] + 1 for value in spec.get('depends', [])), default=0)
        modules[name] = {'module': name, 'depth': depth,
            'version': spec.get('version'), 'license': spec.get('license', 'LGPL-3'),
            'depends': spec.get('depends', []), 'manifest_sha256': sha(manifest),
            'data': files, 'definitions': definitions, 'demo_enabled': False,
            'auto_install': spec.get('auto_install', False)}

    for name in requested:
        visit(name)
    return {'schema': 1, 'requested': requested,
        'minimum_order': sorted(modules.values(), key=lambda row: (row['depth'], row['module'])),
        'actual_auto_install_graph_proven': False, 'numeric_allocations_predicted': False,
        'without_demo': 'all', 'sql_reservation_or_relocation_generated': False}


def checkpoint_queries(aliases, report):
    selected = aliases + [report['original_alias']]
    pks = ','.join(str(row['id']) for row in selected)
    selector = gate.xmlid_selector(selected)
    tables = ','.join(gate.literal(name) for name in gate.TABLES)
    return {
        'transaction': "SELECT current_setting('transaction_read_only') AS mode",
        'modules': "SELECT name,state,license,latest_version,to_jsonb(m)->'demo' AS demo "
            "FROM ir_module_module m WHERE state IN ('installed','to install','to upgrade','to remove') ORDER BY name",
        'tables': "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN (" + tables + ') ORDER BY tablename',
        'metadata_occupants': 'SELECT id,module,name,model,res_id,noupdate FROM ir_model_data WHERE id IN (' + pks
            + ') OR (module,name) IN ' + selector + ' ORDER BY id',
        'action_462': "SELECT a.tableoid::regclass::text AS physical_table,a.id,a.type," 
            "md5(to_jsonb(a)::text) AS row_md5 FROM ir_actions a WHERE a.id=462",
        'action_aliases': "SELECT id,module,name,model,res_id,noupdate FROM ir_model_data "
            "WHERE res_id=462 AND model LIKE 'ir.actions.%' ORDER BY id",
        'binding_models': "SELECT id,model FROM ir_model WHERE id=" + str(report['binding_model_id'])
            + " OR model='hr.payslip' ORDER BY id",
        'sequences': "SELECT s.relname AS sequence_name,p.start_value,p.increment_by,p.max_value,p.min_value,p.cache_size,p.cycle,p.last_value "
            "FROM pg_class s JOIN pg_sequences p ON p.sequencename=s.relname AND p.schemaname='public' "
            "WHERE s.relnamespace='public'::regnamespace AND s.relkind='S' "
            "AND s.relname IN ('ir_actions_id_seq','ir_model_data_id_seq','ir_model_id_seq') ORDER BY s.relname",
    }


def master_queries(tables, capsule):
    result = {}
    available = {row['tablename'] for row in tables}
    rows = gate.capsule_rows(capsule)
    for table in sorted(available & set(gate.TABLES)):
        ids = ','.join(str(row['id']) for row in rows[table])
        result['masters:' + table] = 'SELECT id,md5(to_jsonb(t)::text) AS row_md5 FROM '
        result['masters:' + table] += gate.identifier(table) + ' t WHERE id IN (' + ids + ') ORDER BY id'
        result['count:' + table] = 'SELECT count(*) AS rows FROM ' + gate.identifier(table)
    return result


def assess(capsule, aliases, report, observed, *, runtime_registry=None):
    by_pk = {row['id']: row for row in observed['metadata_occupants']}
    by_name = {key(row): row for row in observed['metadata_occupants']}
    blockers, alias_results = [], []
    for original in aliases + [report['original_alias']]:
        occupant, named = by_pk.get(original['id']), by_name.get(key(original))
        exact = occupant == named == original
        vacant = occupant is None and named is None
        status = 'exact-original-identity' if exact else 'vacant-both-keys' if vacant else 'collision-or-different-metadata-pk'
        if not (exact or vacant):
            blockers.append('original-metadata-pk-or-name-occupied')
        alias_results.append({'original': original, 'pk_occupant': occupant,
            'named_occupant': named, 'status': status, 'mutation_authorized': False})
    if observed['action_462']:
        blockers.append('original-action-462-already-occupied')
    binding = {'id': report['binding_model_id'], 'model': 'hr.payslip'}
    if observed['binding_models'] != [binding]:
        blockers.append('original-binding-model-pk-not-exact-real-payslip-model')
    if observed['action_aliases']:
        blockers.append('action-462-alias-already-bound')
    if any(row['license'] == 'OEEL-1' for row in observed['modules']):
        blockers.append('enterprise-module-in-cold-target')
    if any(row.get('demo') is True for row in observed['modules']):
        blockers.append('demo-module-in-cold-target')
    if any(row['state'] != 'installed' for row in observed['modules']):
        blockers.append('module-graph-not-quiescent')
    if runtime_registry is None or runtime_registry.get('real_community_renderer') is not True:
        blockers.append('real-community-renderer-not-observed-in-registry')
    masters = {table: observed.get('count:' + table, [{'rows': 0}])[0]['rows'] for table in gate.TABLES}
    if any(count for table, count in masters.items() if table != 'hr_payroll_structure_type'):
        blockers.append('salary-seeds-or-adopted-records-already-present')
    type_rows = observed.get('masters:hr_payroll_structure_type', [])
    if masters['hr_payroll_structure_type'] not in (0, 4) or (masters['hr_payroll_structure_type'] == 4
            and {row['id'] for row in type_rows} != {1, 2, 3, 4}):
        blockers.append('noncanonical-or-extra-type-seeds-present')
    type_aliases = [item for item in alias_results if key(item['original']) in TYPE_ALIASES]
    gate.require(len(type_aliases) == 4, 'missing-four-canonical-type-aliases')
    return {'schema': 1, 'read_only': True, 'orm_loaded': False, 'rules_evaluated': False,
        'historical_payroll_read': False, 'database_writes': False,
        'original_alias_count': len(aliases), 'reference_alias_count_not_adopted': 3,
        'report_alias_separate_from_88': report['original_alias'],
        'original_action': report, 'original_action_id_vacant': not observed['action_462'],
        'original_binding_model_identity_exact': observed['binding_models'] == [binding],
        'alias_checks': alias_results, 'canonical_types': type_aliases,
        'master_counts': masters, 'blockers': sorted(set(blockers)),
        'numeric_identity_checkpoint_clear': not blockers,
        # Clear numeric space is necessary, never an import/security/value gate.
        'references_and_original_values_adopted': False, 'import_authorized': False,
        'reservation_authorized': False, 'renumbering_authorized': False,
        'sequence_writes_generated': False, 'conversion_complete': False}


def write_private(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    sources = commands.add_parser('sources', help='Free source inspection only; no database connection')
    sources.add_argument('--source-root', type=Path, action='append', required=True)
    sources.add_argument('--requested', action='append', required=True)
    sources.add_argument('--output', type=Path, required=True)
    checkpoint = commands.add_parser('checkpoint', help='Read-only identity checkpoint; never writes a database')
    for name in ('capsule', 'identity-before', 'source-preflight', 'receipt', 'output'):
        checkpoint.add_argument('--' + name, type=Path, required=True)
    checkpoint.add_argument('--expected-capsule-sha256', required=True)
    checkpoint.add_argument('--database', required=True)
    args = parser.parse_args()
    if args.command == 'sources':
        gate.require(not args.output.exists(), 'new-private-artifact-required')
        report = dependency_minimum(args.source_root, args.requested)
        report['tool_sha256'] = sha(__file__)
        write_private(args.output, report)
        print(json.dumps({'artifact': str(args.output), 'sha256': sha(args.output),
            'minimum_modules': len(report['minimum_order']), 'numeric_allocations_predicted': False}))
        return
    gate.require(args.database.startswith('COMMUNITY_PAYROLL_API_ORIGINAL_BOOTSTRAP_'), 'private-cold-target-required')
    gate.require(args.output.resolve().is_relative_to(Path('/opt/steps-validation'))
        and not args.output.exists(), 'new-private-artifact-required')
    gate.require(stat.S_IMODE(args.capsule.stat().st_mode) == 0o600
        and sha(args.capsule) == args.expected_capsule_sha256, 'private-capsule-digest-mismatch')
    capsule = json.loads(args.capsule.read_text())
    identity = json.loads(args.identity_before.read_text())
    receipt = json.loads(args.receipt.read_text())
    gate.require(receipt['database'] == args.database, 'receipt-database-mismatch')
    aliases = original_aliases(capsule, identity)
    preflight = json.loads(args.source_preflight.read_text())
    gate.require(preflight['capsule_sha256'] == args.expected_capsule_sha256
        and preflight['source_database'] == capsule['database'], 'source-preflight-capsule-provenance-drift')
    report = source_report(preflight, identity)
    statements = checkpoint_queries(aliases, report)
    discovery = gate.run_snapshot(args.database, statements)
    statements.update(master_queries(discovery['tables'], capsule))
    first = gate.run_snapshot(args.database, statements)
    second = gate.run_snapshot(args.database, statements)
    gate.require(first == second and all(first[name] == value for name, value in discovery.items()),
                 'checkpoint-or-catalog-drift')
    result = assess(capsule, aliases, report, first)
    result.update(database=args.database, observations=first, two_snapshots_equal=True,
        provenance={name: {'path': str(path), 'sha256': sha(path)} for name, path in (
            ('capsule', args.capsule), ('identity_before', args.identity_before),
            ('source_preflight', args.source_preflight), ('receipt', args.receipt),
            ('tool', Path(__file__)), ('sql_helper', Path(gate.__file__)))})
    write_private(args.output, result)
    print(json.dumps({'artifact': str(args.output), 'sha256': sha(args.output),
        'original_alias_count': len(aliases), 'numeric_checkpoint_clear': result['numeric_identity_checkpoint_clear'],
        'blockers': result['blockers'], 'import_authorized': False}))


if __name__ == '__main__':
    main()
