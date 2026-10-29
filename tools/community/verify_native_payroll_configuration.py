"""Seal readonly native configuration provenance after an accepted private pair.

Uses the existing SQL-only preflight, then classifies aliases from accepted
identity files. Never loads Odoo, evaluates rules or writes to a database.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

import payroll_configuration_adoption_preflight as gate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_private(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight-root', type=Path, required=True)
    parser.add_argument('--native-root', type=Path, required=True)
    parser.add_argument('--capsule', type=Path, required=True)
    parser.add_argument('--expected-capsule-sha256', required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    for path in (args.preflight_root, args.native_root, args.capsule):
        assert Path('/opt/steps-validation') in path.resolve().parents
    assert stat.S_IMODE(args.capsule.stat().st_mode) == 0o600
    assert sha(args.capsule) == args.expected_capsule_sha256
    capsule = read(args.capsule)
    gate.capsule_rows(capsule)
    folder = args.preflight_root / 'evidence'
    source_path = folder / 'native-source.json'
    classification_path = folder / 'native-xmlid-classification.json'
    assert not source_path.exists() and not classification_path.exists()
    native = args.native_root / 'cerro-reference'
    acceptance_path = native / 'passed.json'
    accepted = read(acceptance_path)
    database = accepted['database']
    assert database.startswith('MANAGEMENT_QA_CERRO_PAYROLL_API_')
    assert accepted['mode'] == 'cerro-reference' and accepted['counts']['enterprise'] == 140
    assert not accepted['writes_to_source'] and not accepted['historical_conversion']
    assert sha(native / 'source-files.json') == accepted['source_files_sha256']
    tool_path = Path(gate.__file__)
    assert read(folder / 'before.json')['tool_sha256'] == read(folder / 'after.json')['tool_sha256'] == sha(tool_path)
    statements = gate.queries(capsule, source=True)
    # Counts are added separately; the shared helper's public schema is kept.
    statements.update({
        'row_count:' + table: 'SELECT count(*) AS row_count FROM ' + gate.identifier(table)
        for table in capsule['tables']})
    before = gate.run_snapshot(database, statements)
    after = gate.run_snapshot(database, statements)
    assert before == after and before['transaction'] == [{'mode': 'on'}]
    tables = []
    for table, values in capsule['tables'].items():
        count = before['row_count:' + table][0]['row_count']
        digest = before['source_hash:' + table][0]['rows_sha256']
        assert count == values['row_count'] and digest == values['rows_sha256']
        tables.append({'table': table, 'capsule_row_count': count, 'native_row_count': count,
            'capsule_rows_sha256': digest, 'native_rows_sha256': digest, 'rows_and_count_equal': True})
    assert sum(row['native_row_count'] for row in tables if row['table'] in gate.TABLES) == 120
    attributes = {'type': 'ttype', 'relation': 'relation', 'required': 'required', 'readonly': 'readonly',
        'store': 'store', 'related': 'related', 'company_dependent': 'company_dependent'}
    fields = {(row['model'], row['name']): row for row in before['fields']}
    for field in capsule['field_metadata']:
        assert all(field[key] == fields[field['model'], field['name']][target] for key, target in attributes.items())
    key = lambda row: (row['module'], row['name'])
    expected = {key(row): row for row in capsule['xmlids']}
    actual = {key(row): row for row in before['xmlids']}
    assert len(expected) == len(capsule['xmlids']) == 91 and expected.keys() == actual.keys()
    references = {('step_simpledigital_oca_security', 'chile_rule_' + name) for name in ('basic', 'gross', 'net')}
    drift = []
    for ident, row in expected.items():
        differences = [name for name, value in row.items() if actual[ident][name] != value]
        if differences:
            assert ident in references and differences == ['id']
            drift.append({'xmlid': '.'.join(ident), 'differences': differences, 'original': row, 'native': actual[ident]})
    assert len(drift) == 3
    report = {'schema': 1, 'read_only': True, 'orm_loaded': False, 'rules_evaluated': False,
        'historical_payroll_read': False, 'salary_formulas_exposed': False,
        'source_capsule_database': capsule['database'], 'native_database': database,
        'capsule_sha256': sha(args.capsule), 'tool_path': str(tool_path), 'tool_sha256': sha(tool_path),
        'generator_sha256': sha(Path(__file__)), 'native_acceptance_path': str(acceptance_path),
        'native_acceptance_sha256': sha(acceptance_path), 'tables': tables, 'source_master_count': 120,
        'all_six_table_hashes_and_counts_equal': True, 'original_xmlid_count': len(expected),
        'original_xmlids_exactly_preserved': False, 'xmlid_drift': drift,
        'capsule_field_metadata_preserved': True, 'field_metadata_drift': [],
        'two_readonly_snapshots_equal': True, 'native_metadata_before': before, 'native_metadata_after': after,
        'before_metadata_sha256': gate.digest(before), 'after_metadata_sha256': gate.digest(after),
        'adoption_authorized': False, 'engine_converted': False, 'financial_certified': False}
    # Classification is a file-only proof, not another database observation.
    prior = read(native / 'identity-before.json')['original_xmlids']
    later = read(native / 'identity-after.json')['original_xmlids']
    prior_map, later_map = {key(row): row for row in prior}, {key(row): row for row in later}
    assert len(prior_map) == len(prior) and all('noupdate' in row for row in prior)
    assert all(row == later_map[ident] for ident, row in prior_map.items())
    assert references.isdisjoint(prior_map)
    origins = []
    additions = []
    for ident, row in expected.items():
        if ident in references:
            additions.append({'xmlid': '.'.join(ident), 'capsule': row, 'native_after': actual[ident]})
        else:
            assert row == actual[ident] == prior_map[ident]
            origins.append({'xmlid': '.'.join(ident), 'capsule': row, 'native_before': prior_map[ident],
                'native_after': actual[ident], 'before_vs_capsule_differences': [], 'capsule_vs_native_after_differences': []})
    assert len(origins) == 88 and len(additions) == 3
    write_private(source_path, report)
    hooks = args.native_root / 'addons/step_simpledigital_oca_security/hooks.py'
    classification = {'schema': 1, 'read_only_files_only': True, 'database_queried': False, 'orm_loaded': False,
        'source_acceptance_path': str(acceptance_path), 'capsule_sha256': sha(args.capsule),
        'capsule_source_database': capsule['database'], 'native_database': database,
        'identity_before_path': str(native / 'identity-before.json'), 'identity_before_sha256': sha(native / 'identity-before.json'),
        'identity_after_path': str(native / 'identity-after.json'), 'identity_after_sha256': sha(native / 'identity-after.json'),
        'identity_before_xmlid_count': len(prior), 'identity_before_noupdate_captured': True,
        'all_original_xmlids_and_noupdate_preserved': True, 'all_original_xmlid_drift': [],
        'native_provenance_path': str(source_path), 'native_provenance_sha256': sha(source_path),
        'capsule_xmlid_count': len(expected), 'origin_xmlids_present_before_upgrade': 88,
        'origin_xmlid_core_fields_and_noupdate_exactly_equal': True, 'reference_aliases_absent_before_upgrade': 3,
        'reference_alias_records': additions, 'origin_alias_records': origins, 'unexpected_drift': [],
        'before_capture_does_not_include_noupdate': False,
        'all_91_named_references_and_noupdate_match_capsule_and_native': True,
        'adapter_source': {'path': str(hooks), 'sha256': sha(hooks), 'creation_function': 'post_init_hook'},
        'classification': '88 original XML IDs with noupdate, plus 3 new reference-adapter aliases',
        'capsule_not_91_original_metadata_primary_keys': True, 'adoption_authorized': False, 'financial_certified': False}
    write_private(classification_path, classification)
    print(json.dumps({'native_database': database, 'master_count': 120, 'original_xmlids': len(prior),
        'origin_aliases': 88, 'reference_aliases': 3, 'snapshots_equal': True, 'writes_to_database': False}))


if __name__ == '__main__':
    main()
